# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import uuid, os, logging, sys, multiprocessing, tempfile

class E2EEvaluator:
    def __init__(self, testcase, codegen_folder = "cuda_codegen", default_device = "CUDA", working_foler = ".", nnfusion_cli = "", nnfusion_cli_arg = "", perf_mode = False):
        self.codegen_folder = codegen_folder
        self.default_device = default_device
        self.testcase = testcase
        self.working_foler = working_foler
        if not os.path.exists(nnfusion_cli):
            self.nnfusion_cli = self.load_default_nnfusion_cli()
        else:
            self.nnfusion_cli = nnfusion_cli
        self.nnfusion_cli_arg = nnfusion_cli_arg

        self.perf_mode = False
        self.latency = 0
    
    def load_default_nnfusion_cli(self):
        nnf_clis = [os.path.join(os.path.dirname(os.path.abspath(
            __file__)), "../../../build/src/tools/nnfusion/nnfusion"), "/usr/local/bin/nnfusion"]
        for nnf in nnf_clis:
            if os.path.exists(nnf):
                print(f"NNFusion CLI detected: {nnf}")
                return nnf
        logging.error("No nnfusion cli available.")
        exit(1)

    def nnfusion_compile(self):
        logging.info(f"Compiling {self.testcase.get_filename()}")

        name, suf = os.path.splitext(self.testcase.get_filename())
        modeltype = "-f tensorflow"
        if suf == ".onnx":
            modeltype = "-f onnx"
        elif suf == ".pt":
            modeltype = "-f torchscript"

        logging.info(
            f"cd {self.working_foler} && {self.nnfusion_cli} {self.testcase.get_filename()} {modeltype} {self.testcase.flag} -fdefault_device={self.default_device} {self.nnfusion_cli_arg} >> nnfusion.log"
        )

        os.system(
            f"cd {self.working_foler} && {self.nnfusion_cli} {self.testcase.get_filename()} {modeltype} {self.testcase.flag} -fdefault_device={self.default_device} {self.nnfusion_cli_arg} >> nnfusion.log"
        )
        if not os.path.exists(
            f"{self.working_foler}/nnfusion_rt/{self.codegen_folder}/nnfusion_rt.h"
        ):
            logging.error("Failed at nnfusion compiling phase.")
            return False
        return True
    
    def build(self):
        os.system(
            f"cd {self.working_foler}/nnfusion_rt/{self.codegen_folder}/ && cmake . >> cmake.log && make -j 2>&1 >> cmake.log"
        )
        if not os.path.exists(
            f"{self.working_foler}/nnfusion_rt/{self.codegen_folder}/main_test"
        ):
            logging.error("Failed at compiling phase.")
            return False
        return True
    
    def allclose(self):
        code = os.system(
            f"cd {self.working_foler}/nnfusion_rt/{self.codegen_folder}/ && ./main_test > result.txt"
        )
        if code != 0:
            logging.error(f"{self.testcase.casename} execution failed.")
            return False
        if not os.path.exists(
            f"{self.working_foler}/nnfusion_rt/{self.codegen_folder}/result.txt"
        ):
            logging.error("Failed at compiling phase.")
            return False
        result_file = open(
            f"{self.working_foler}/nnfusion_rt/{self.codegen_folder}/result.txt"
        )
        results = result_file.readlines()
        if not self.testcase.allclose(results):
            logging.error(f"{self.testcase.casename} result missmatch.")
            return False
        return True 
    
    def exectime(self):
        code = os.system(
            f"cd {self.working_foler}/nnfusion_rt/{self.codegen_folder}/ && ./main_test > result.txt"
        )
        if code != 0:
            logging.error(f"{self.testcase.casename} execution failed.")
            return False
        if not os.path.exists(
            f"{self.working_foler}/nnfusion_rt/{self.codegen_folder}/result.txt"
        ):
            logging.error("Failed at compiling phase.")
            return False
        result_file = open(
            f"{self.working_foler}/nnfusion_rt/{self.codegen_folder}/result.txt"
        )
        results = result_file.readlines()
        latency = self.testcase.latency(results)
        return latency

    def report(self):
        os.system(f"rm -rf {self.working_foler}/nnfusion_rt")
        if not self.nnfusion_compile():
            os.system(f"rm -rf {self.working_foler}/nnfusion_rt")
            return False
        if not self.build():
            os.system(f"rm -rf {self.working_foler}/nnfusion_rt")
            return False

        if self.perf_mode is False:
            if not self.allclose():
                os.system(f"rm -rf {self.working_foler}/nnfusion_rt")
                return False
        else:
            self.latency = self.exectime()

        os.system(f"rm -rf {self.working_foler}/nnfusion_rt")
        return True

configs = {"CUDA" : ["cuda_codegen", "CUDA"], "ROCM" : ["rocm_codegen", "ROCm"], "CPU" : ["cpu_codegen","CPU"]}

def E2EExecutor(TestCases, devname, report_list, nnf, nnf_args):
    tmpdir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
    logging.info(f"create {tmpdir}")
    os.mkdir(tmpdir) # working folder

    for test in TestCases:
        logging.info(f"Testing {test.casename}")
        if test.valid():
            perf_mode = "latency" in dir(test)
            eval = E2EEvaluator(test, configs[devname][0], configs[devname][1], tmpdir, nnf, nnf_args, perf_mode)
            report = devname + "\t" + test.casename + '\t' + ",".join(test.tags) + "\t";
            if eval.report():
                report += "Succeed!"
            else:
                eval = E2EEvaluator(test, configs[devname][0], configs[devname][1], tmpdir)
                report += ",\tSucceed" if eval.report() else ",\tFailed"
            if eval.perf_mode:
                report += ",\t" + str(eval.latency)
            logging.info(report)
            report_list.append(report)
    # clean
    logging.info(f"remove {tmpdir}")
    os.system(f"rm -rf {tmpdir}")

def CLIExecutor(info, report_list):
    print(info)
    side_cli = str(os.environ.get('SIDECLI', ''))
    if os.system(side_cli) == 0:
       report_list.append(side_cli + "\tSucceed!") 
    else:
       report_list.append(side_cli + "\tFailed") 

import os, sys, logging
from ctypes import *
import dtypes

class Runtime:
    def __init__(self):
        # detect existed library of nnfusion runtime
        libnnf_rt = "none"
        if "LIB_NNF_RT" in os.environ:
            libnnf_rt = os.environ["LIB_NNF_RT"]

        else:
            logging.info("libnnfusion_rt is not specified by system enviroment variable: LIB_NNF_RT")
            default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
            for file in os.listdir(default_path):
                if file.startswith("libnnf") and file.endswith("rt.so"):
                    libnnf_rt = os.path.join(default_path, file)
                    logging.info("libnnfusion_rt library detected")
            self.default_path = default_path
        if not os.path.exists(libnnf_rt):
            raise Exception(f"libnnfusion_rt: {libnnf_rt} is not existed!")

        try:
            libnnf = cdll.LoadLibrary(libnnf_rt)
        except:
            raise Exception(f"libnnfusion_rt: {libnnf_rt} is not loaded!")

        # member of session
        self.libnnf_path = libnnf_rt
        self.libnnf = libnnf
    
    # call for init session
    def init(self):
        if "cpu" in self.libnnf_path:
            self.libnnf.cpu_init()
        else:
            self.libnnf.cuda_init()

    def feed(self, tensors = [], signature = (), params = ()):
        if tensors is not []:
            self.libnnf.argtypes = dtypes.deduce_signatrue(tensors)
            self.libnnf.kernel_entry(*(dtypes.get_data_addr(tensors)))
        else:
            self.libnnf.argtypes = signature
            self.libnnf.kernel_entry(*params)

    def free(self):
        if "cpu" in self.libnnf_path:
            self.libnnf.cpu_free()
        else:
            self.libnnf.cuda_free()
        
        del self.libnnf
        del self.libnnf_path
class Config:
    def __init__(self):
        self.decompose_mode = 'cswap_decompose' 
        # self.decompose_mode = 'subspace_decompose'
        self.load_bus = True
        self.dcswap_embedding = False
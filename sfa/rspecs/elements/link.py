from sfa.rspec.elements.interface import Interface

class Link:
    def __init__(self):
        self.component_id = None
        self.component_name = None
        self.component_manager_id = None
        self.type = None
        self.endpoint1 = Interface()
        self.endpoint2 = Interface()
        self.capacity = None
        self.latency = None
        self.packet_loss = None
        self.description = None

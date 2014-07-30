from nova.exception import ImageNotFound
from sfa.rspecs.elements.disk_image import DiskImage


class Image:
    
    def __init__(self, image=None):
        if image is None: image={}
        self.id = None
        self.container_format = None
        self.kernel_id = None
        self.ramdisk_id = None
        self.properties = None
        self.name = None
        self.description = None
        self.os = None
        self.version = None

        if image:
            self.parse_image(image)

    def parse_image(self, image):
        if isinstance(image, dict):
            self.id = image['id'] 
            self.name = image['name']
            self.container_format = image['container_format']
            self.properties = image['properties'] 
            if 'kernel_id' in self.properties:
                self.kernel_id = self.properties['kernel_id']
            if 'ramdisk_id' in self.properties:
                self.ramdisk_id = self.properties['ramdisk_id']
   
    def to_rspec_object(self):
        img = DiskImage()
        img['name'] = self.name
        img['description'] = self.name
        img['os'] = self.name
        img['version'] = self.name
        return img     

class ImageManager:

    def __init__(self, driver):
        self.driver = driver

    @staticmethod
    def disk_image_to_rspec_object(image):
        img = Image(image)
        return img.to_rspec_object()

    def get_available_disk_images(self):
        # get image records
        disk_images = []
        for img in self.driver.shell.image_manager.get_images_detailed():
            image = Image(img)
            if image.container_format in ['ami', 'ovf']:
                disk_images.append(image)
        return disk_images

    def get_disk_image(self, id=None, name=None):
        """
        Look up a image bundle using the specifeid id or name
        """
        disk_image = None
        try:
            if id:
                image = self.driver.shell.nova_manager.images.find(id=id)
            elif name:
                image = self.driver.shell.nova_manager.images.find(name=name)
        except ImageNotFound:
                pass
        return Image(image)

    

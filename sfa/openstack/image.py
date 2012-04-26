from nova.exception import ImageNotFound
from sfa.rspecs.elements.disk_image import DiskImage

class Image:

    def __init__(self, driver):
        self.driver = driver

    @staticmethod
    def disk_image_to_rspec_object(image):
        img = DiskImage()
        img['name'] = image['ami']['name']
        img['description'] = image['ami']['name']
        img['os'] = image['ami']['name']
        img['version'] = image['ami']['name']
        return img

    def get_available_disk_images(self):
        # get image records
        disk_images = []
        for image in self.driver.shell.image_manager.detail():
            if image['container_format'] == 'ami':
                disk_images.append(self.get_machine_image_details(image))
        return disk_images

    def get_machine_image_details(self, image):
        """
        Returns a dict that contains the ami, aki and ari details for the specified
        ami image.
        """
        disk_image = {}
        if image['container_format'] == 'ami':
            kernel_id = image['properties']['kernel_id']
            ramdisk_id = image['properties']['ramdisk_id']
            disk_image['ami'] = image
            disk_image['aki'] = self.driver.shell.image_manager.show(kernel_id)
            disk_image['ari'] = self.driver.shell.image_manager.show(ramdisk_id)
        return disk_image

    def get_disk_image(self, id=None, name=None):
        """
        Look up a image bundle using the specifeid id or name
        """
        disk_image = None
        try:
            if id:
                image = self.driver.shell.image_manager.show(id)
            elif name:
                image = self.driver.shell.image_manager.show_by_name(name)
            if image['container_format'] == 'ami':
                disk_image = self.get_machine_image_details(image)
        except ImageNotFound:
                pass
        return disk_image

    

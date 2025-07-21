import numpy
from cellprofiler_core.module import Module
from cellprofiler_core.setting.subscriber import LabelSubscriber, ImageSubscriber
from cellprofiler_core.setting.text import Float, ImageName
from cellprofiler_core.object import Objects
from cellprofiler_core.image import Image

class NormalizeIntensity(Module):
    module_name = "NormalizeIntensity"
    category = "Image Processing"
    variable_revision_number = 1

    def create_settings(self):
        # Select objects to be used for masking the normalization regions
        self.object_name = LabelSubscriber(
            "Select objects to normalize",
            "None",
            doc="""\
Choose the objects (from a previous module) that you wish to process. 
Each object will be normalized separately using its own pixel region.
"""
        )
        # Select the input image to normalize
        self.image_name = ImageSubscriber(
            "Select the image to normalize",
            "None",
            doc="""\
Choose the image that contains the intensity values to be normalized.
"""
        )
        # Factor to scale the intensities within each object
        self.scale_factor = Float(
            "Scale Factor",
            1.0,
            doc="""\
Enter the scale factor to multiply the intensity values inside each object.
"""
        )
        # Constant to add after scaling
        self.add_constant = Float(
            "Add Constant",
            0.0,
            doc="""\
Enter the constant to be added to the intensity values following scaling.
"""
        )
        # Name for the output image so that it can be reused downstream in the pipeline
        self.output_image_name = ImageName(
            "Name of output image",
            "NormalizedImage",
            doc="""\
Enter the name for the normalized output image. This name is used both for displaying 
the image when the module’s window is visible and for accessing the image in subsequent modules.
"""
        )

    def settings(self):
        return [
            self.object_name,
            self.image_name,
            self.scale_factor,
            self.add_constant,
            self.output_image_name
        ]

    def visible_settings(self):
        return self.settings()

    def run(self, workspace):
        # Retrieve the objects (label matrix) and the image from the workspace
        objects = workspace.object_set.get_objects(self.object_name.value)
        labels = objects.segmented
        image = workspace.image_set.get_image(self.image_name.value)
        image_data = image.pixel_data.astype(float)
        
        # Iterate through each object (ignoring the background, label 0)
        for obj_label in numpy.unique(labels):
            if obj_label == 0:
                continue  # Skip background
            # Create a mask for the current object
            mask = labels == obj_label
            # Extract the intensity values for the object region
            region_intensity = image_data[mask]
            # Perform custom normalization (scaling and addition)
            normalized = (region_intensity * self.scale_factor.value) + self.add_constant.value
            image_data[mask] = normalized

        # Create a new image for the normalized data so that it propagates
        # downstream and is available for display.
        output_image = Image()
        output_image.pixel_data = image_data
        workspace.image_set.add_image(output_image, self.output_image_name.value)
        
        # If the module window is active, save the normalized image for display purposes
        if self.show_window:
            workspace.display_data.normalized_image = image_data

    def display(self, workspace, figure):
        # Retrieve the normalized image saved in run
        normalized_image = workspace.display_data.normalized_image
        figure.set_subplots((1, 1))
        figure.subplot_imshow(0, 0, normalized_image,
                              title=self.output_image_name.value)

#################################
#
# Imports from useful Python libraries
#
#################################

import numpy as np
import scipy.ndimage
import scipy
import skimage
from _utils import iterate_mask

#################################
#
# Imports from CellProfiler
#
##################################


__doc__ = """\
Measure RDF
===================

**Measure RDF** - Estimate radial distribution function from a set of
objects.

Given an object collection and image, estimates the radial distribution
function (RDF) of each object for each channel in the image.  If provided,
masks will be respected by only supporting estimates in the masked region.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO           YES
============ ============ ===============

What do I need as input?
^^^^^^^^^^^^^^^^^^^^^^^^

Assumes each channel is properly aligned and intensity is roughly additive.
The additive assumption corrects for objects too close togher.

What do I get as output?
^^^^^^^^^^^^^^^^^^^^^^^^

An average RDF for all objects in the image is displayed for each channel.
Per object results can be saved as measurements.

Measurements made by this module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This module makes the following measurements:

**RDF** (the RDF category):

-  *Intensity_[IMAGE_NAME]_O[Oi]_C[Ci]_R[Ri]*: the raw estimated radial
   intensity for channel Ci at pixel position Ri for object Oi

-  *Counts_[IMAGE_NAME]_O[Oi]_R[Ri]*: the number of pixels contributing
   to the estimated intensity

Technical notes
^^^^^^^^^^^^^^^

The RDF curve is estimated for each parent object using every input object
as a source.  Using scipy.optimize.curve_fit, the estimated RDF is optimized
assuming each pixel contains the summed intensity from each source.  While
superposition is not likely true in most cases, fitting to the mean centered,
unit variance intensity can improve the estimate.

References
^^^^^^^^^^

-  *Viscoelastic RNA entanglement and advective flow underlie nucleolar form and function*
   Joshua A. Riback, Jorine M. Eeftens, Daniel S. W. Lee, Sofia A.
   Quinodoz, Lien Beckers, Lindsay A. Becker, Clifford P. Brangwynne
   (`link <https://doi.org/10.1101/2021.12.31.474660>`__)
"""

from cellprofiler_core.constants.measurement import COLTYPE_FLOAT
from cellprofiler_core.module import Module
from cellprofiler_core.setting import ValidationError, Binary
from cellprofiler_core.setting.subscriber import ImageSubscriber, LabelSubscriber
from cellprofiler_core.setting.text import Integer, Text

C_MEASUREMENT_RDF = "RDF"


class MeasureRdf(Module):
    module_name = "MeasureRdf"
    category = "Measurement"
    variable_revision_number = 1

    def create_settings(self):
        self.input_image_name = ImageSubscriber(
            text="Input image",
            doc="""\
Each channel will have an RDF estimate independently.  Perform any background
correction prior to this measurement.

**MeasureRdf** will estimate the radial distribution of intensity for each
object.
""",
        )

        self.input_object_name = LabelSubscriber(
            text="Input objects",
            doc="Each object center will be taken as a source, grouped by parent id",
        )

        self.input_object_mask = LabelSubscriber(
            text="Object masks",
            doc="Limit estimation of RDF to only the masked area.",
        )

        self.radius = Integer(
            text="RDF radius",
            value=20,
            minval=1,
            maxval=50,
            doc="The maximum distance in pixels to estimate RDF.",
        )

        self.channels = Text(
            text="Channels",
            value="1,2",
            doc="Comma separated list of channels to estimate.",
        )

        self.measure_type = Binary(
            text="Consider rdf from point",
            value=True,
            doc="Select yes for point-based rdf, no for rim based"
        )

    def validate_module(self, pipeline):
        try:
            channels = self.get_channels()
        except:
            raise ValidationError(
                "Unable to parse channels, must be a comma separated list of integers.",
                self.channels,
            )
        if len(channels) == 0:
            raise ValidationError(
                "Channels must not be empty.",
                self.channels,
            )

    def get_channels(self):
        result = [int(token.strip()) - 1 for token in self.channels.value.split(',')]
        return result

    def settings(self):
        return [self.input_image_name,
                self.input_object_name,
                self.input_object_mask,
                self.radius,
                self.channels,
                self.measure_type
                ]

    def run(self, workspace):

        input_image_name = self.input_image_name.value
        input_object_name = self.input_object_name.value
        input_object_mask = self.input_object_mask.value

        input_image = workspace.image_set.get_image(input_image_name, must_be_grayscale=False)
        pixels = input_image.pixel_data  # x by y by channels

        targets = workspace.object_set.get_objects(input_object_name)
        support = workspace.object_set.get_objects(input_object_mask)

        channels = self.get_channels()

        self.intens = []
        self.counts = []
        self.bins = []


        if self.measure_type.value is True:  # point-based
            self.bins, self.intens, self.counts = self.rdf_image(pixels, targets, support, self.radius.value, channels)
        else:  # rim based
            self.bins, self.intens, self.counts = self.rdf_boundary(pixels, targets, support, self.radius.value, channels)

        measurements = workspace.measurements

        print(f"Started run for {input_image_name}")
        print(f"RDF bins: {self.bins}")
        print(f"RDF intensities: {self.intens}")

        if len(self.intens) != 0 and len(self.counts) != 0: # Added check for empty intens and counts
            for channel, intens in zip(channels, self.intens):
                for radius, intens in zip(self.bins, intens):
                    feature = (
                            f"{C_MEASUREMENT_RDF}_"
                            "Intensity_"
                            f"C{channel+1}_"
                            f"R{radius}"
                    )
                    measurements.add_measurement(input_object_mask, feature, intens)
            for radius, counts in zip(self.bins, self.counts):
                measurements.add_measurement(input_object_mask, f"{C_MEASUREMENT_RDF}_Counts_R{radius}", counts)

    #
    # "display" lets you use matplotlib to display your results.
    #
    def display(self, workspace, figure):
        # need 1 + number of channels plots
        channels = self.get_channels()
        rows = 1
        if len(channels) > 2:
            rows = 2

        cols = int(np.ceil((len(channels)+1) / rows))

        figure.set_subplots((cols, rows))

        ax = None
        
        ax_list = []
        labels = []

        if not (hasattr(self, "bins") or hasattr(self, "intens") or hasattr(self, "counts")):
            figure.set_subplots((1, 1))
            ax = figure.subplot(0, 0)
            ax.text(0.5, 0.5, "RDF data not available yet", horizontalalignment='center', verticalalignment='center')
            return
        else:

            print(f"Started display for {self.input_image_name.value}")
            print(f"RDF bins: {self.bins}")
            print(f"RDF intensities: {self.intens}")

            for i, (channel, intens) in enumerate(zip(channels, self.intens)):
                x, y = i % cols, i // cols
                ax = figure.subplot(x, y, sharex=ax)
                ax_list.append(ax)
                ax.plot(self.bins, intens, label=f"Obj {i+1}")

                labels.append(f"Obj {i+1}")

                ax.set_xlabel('Radius (px)')
                ax.set_ylabel('Raw Intensity')
                ax.legend(loc='upper right') # added legend for each channel
                figure.set_subplot_title(f"Channel {channel+1}", x, y)

            #  plot average on same axis
            i += 1
            x, y = i % cols, i // cols
            ax = figure.subplot(x, y, sharex=ax)
            intens = np.nansum(self.intens * self.counts, axis=-1) / self.counts.sum(axis=-1)
            intens = ((intens - intens.min(axis=1, keepdims=True)) 
            / (intens.max(axis=1, keepdims=True) - intens.min(axis=1, keepdims=True)))
            for i, channel in enumerate(channels):
                ax.plot(self.bins, intens[i], label=f"C{channel+1}")

            ax.legend(loc='upper right')

            ax.set_xlabel('Radius (px)')
            ax.set_ylabel('Normalized Intensity')
            figure.set_subplot_title(f"Image Average", x, y)

        # figure.legend(ax_list, labels=labels,
        #         loc="upper right")

    # We have to tell CellProfiler about the measurements we produce.
    # There are two parts: one that is for database-type modules and one
    # that is for the UI. The first part gives a comprehensive list
    # of measurement columns produced. The second is more informal and
    # tells CellProfiler how to categorize its measurements.
    #
    # "get_measurement_columns" gets the measurements for use in the database
    # or in a spreadsheet. Some modules need this because they
    # might make measurements of measurements and need those names.
    #
    def get_measurement_columns(self, pipeline):
        channels = self.get_channels()

        radius = self.radius.value
        radii = np.linspace(-radius, radius+1, 2*radius+2, dtype=int)[:-1]
        if self.measure_type.value is True:
            radii = np.arange(radius + 1, dtype=int)

        return [
            (self.input_object_mask.value, f"{C_MEASUREMENT_RDF}_Intensity_C{channel+1}_R{radius}", COLTYPE_FLOAT)
            for channel in channels
            for radius in radii
        ] + [
                (self.input_object_mask.value, f"{C_MEASUREMENT_RDF}_Counts_R{radius}", COLTYPE_FLOAT)
                for radius in radii
            ]

    #
    # "get_categories" returns a list of the measurement categories produced
    # by this module. It takes an object name - only return categories
    # if the name matches.
    #
    def get_categories(self, pipeline, object_name):
        if object_name == self.input_object_mask:
            return [C_MEASUREMENT_RDF]

        return []

    #
    # Return the feature names if the object_name and category match
    #
    def get_measurements(self, pipeline, object_name, category):
        if object_name == self.input_object_mask and category == C_MEASUREMENT_RDF:
            return ["Intensity", "Counts"]

        return []

    #
    # This module makes per-image measurements. That means we need
    # "get_measurement_images" to distinguish measurements made on two
    # different images by this module
    #
    def get_measurement_images(self, pipeline, object_name, category, measurement):
        if measurement in self.get_measurements(pipeline, object_name, category):
            return [self.input_image_name.value]

        return []

    def get_measurement_scales(
        self, pipeline, object_name, category, measurement, image_name
    ):
        """Get the scales for a measurement

        For the Zernikes, the scales are of the form, N2M2 or N2MM2 for
        negative azimuthal degree
        """

        return []

    @staticmethod
    def rdf_fit(
        image, mask, centers, radius, channels,
    ):
        """Predict rdf by optimizing an RDF to the entire image,
        consider only targets within radius of each pixel"""

        # find each targets distance
        mask_inds = np.stack(np.where(mask), axis=-1) # Get coordinates of the mask pixels
        p_dists = scipy.spatial.distance.cdist(mask_inds, centers)  # Create a [euclidean] dist transform matrix having shape (n_mask_pixels, n_centers) - 
        p_dists[p_dists > radius] = -1 # Change values in rows where distance is greater than radius to -1
        p_dists = p_dists.round().astype(int)

        # remove pixels with no support
        no_info = np.all(p_dists == -1, axis=-1) # Check if all distances in a row are -1
        mask[mask] = ~no_info # Retain mask pixels that are within the radius of at least one center
        p_dists = p_dists[~no_info]

        if mask.sum() < radius * 10:  # not enough points to fit
            return np.zeros((len(channels), radius + 1)), np.zeros((radius + 1,))

        # find number of pixels with support at each distance (treats the whole array as flat since axis is not specified)

        # ADDED: Find unique values per row, concatenate them, and then find unique values and their counts
        # unique_vals_per_row = [np.unique(row) for row in p_dists]
        # all_row_uniques = np.concatenate(unique_vals_per_row)
        # values, raw_counts = np.unique(all_row_uniques, return_counts=True)
        
        values, raw_counts = np.unique(p_dists, return_counts=True)

        # fill in all distances with zero (in case some are absent),
        counts = np.zeros((radius + 1,))
        counts[values[1:]] = raw_counts[1:] # remove the -1; values -> [-1, 0, 1, 2, ..., radius+1]

        intensities = np.zeros((len(channels), radius + 1))

        def rdf_translate(x, *rdf_est):
            """Translate the distances in x to total intensity based on rdf"""
            # index into distances
            dists = p_dists[x.astype(int), :]
            # convert to np array with 0 for the `-1` of pixels outside of distance
            params = np.append(rdf_est, 0.0)
            # sum intensity of each target
            return params[dists].sum(axis=1)

        for i, channel in enumerate(channels):
            img = image[mask, channel]
            # mean center
            im_mean = img.mean()
            im_std = img.std()
            # Standardize the image intensity before RDF
            img = (img - im_mean) / im_std
            # estimate rdf
            rdf, _ = scipy.optimize.curve_fit(
                rdf_translate, np.arange(p_dists.shape[0]), img, p0=intensities[i]
            )
            # revert mean centering
            intensities[i, :] = rdf * im_std + im_mean

        return intensities, counts

    @staticmethod
    def rdf_image(
        image,
        target_objects,
        support_objects,
        radius: int,
        channels,
    ):
        intens = []
        counts = []
        distances = np.arange(radius + 1, dtype=int)
        targets = target_objects.center_of_mass()
        for image, support_mask, top_left in iterate_mask(image, support_objects):
            targets_in_support = targets[
                (targets[:, 0] > top_left[0]) &
                (targets[:, 1] > top_left[1]) &
                (targets[:, 0] < top_left[0] + image.shape[0]) &
                (targets[:, 1] < top_left[1] + image.shape[1]), :
            ] - top_left
            if len(targets_in_support) > 0:
                intens_, counts_ = MeasureRdf.rdf_fit(
                    image,
                    support_mask,
                    targets_in_support,
                    radius,
                    channels,
                )
                intens.append(intens_)
                counts.append(counts_)
            else:
                intens.append(np.zeros((len(channels), radius + 1)))
                counts.append(np.zeros((radius + 1,)))

        return distances, np.stack(intens, axis=-1), np.stack(counts, axis=-1)

    @staticmethod
    def rdf_boundary(
        image,
        target_objects,
        support_objects,
        radius,
        channels,
        ):
        intens = []
        counts = []
        bins = np.arange(-radius-1, radius+3, dtype=int)
        targets = target_objects.segmented
        for image, support_mask, top_left in iterate_mask(image, support_objects):
            targets_in_support = targets[
                top_left[0]:top_left[0] + image.shape[0],
                top_left[1]:top_left[1] + image.shape[1],
            ] # Should we be doing image.shape[0] + top_left[0]?
            if len(np.unique(targets_in_support)) > 1:
                intens_, counts_ = MeasureRdf.measure_boundary(
                    image,
                    support_mask,
                    targets_in_support,
                    radius,
                    channels,
                    bins,
                )
                intens.append(intens_)
                counts.append(counts_)
            else:
                intens.append(np.zeros((len(channels), len(bins)-3)))
                counts.append(np.zeros((len(bins)-3,)))

        if intens:
            return bins[1:-2], np.stack(intens, axis=-1), np.stack(counts, axis=-1)
        return bins[1:-2], [], []

    @staticmethod
    def measure_boundary(image, mask, targets, radius, channels, bins):
        boundary = skimage.segmentation.find_boundaries(targets, mode='inner')
        supports = skimage.morphology.binary_dilation(
            boundary, footprint=skimage.morphology.disk(radius+1))

        boundary_inds = np.stack(np.where(boundary), axis=-1)
        support_inds = np.stack(np.where(supports), axis=-1)

        p_dists = scipy.spatial.distance.cdist(support_inds, boundary_inds)
        p_dists[p_dists > radius+1] = -1

        dists = np.zeros(mask.shape, dtype=int)
        dists[supports] = np.ma.masked_array(p_dists, p_dists == -1).min(axis=1)
        dists[targets != 0] *= -1

        counts = np.histogram(dists[supports & mask], bins)[0]

        intens = np.zeros((len(channels), len(bins)-1))
        for i, channel in enumerate(channels):
            intens[i] = np.histogram(dists[supports & mask], bins, weights=image[supports & mask, channel])[0]

        # strip out the first and last (extra) bins
        intens, counts = intens[:, 1:-1], counts[1:-1]
        # normalize intens by counts
        intens = intens / counts
        return intens, counts

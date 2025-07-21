import numpy as np


def iterate_mask(image, mask):
    if image.ndim == 2:
        image = np.expand_dims(image, axis=-1)

    for i in mask.indices:
        if i == 0:
            continue
        current_mask = mask.segmented == i

        rows, cols, top_left = bounding_box(current_mask)

        current_mask = current_mask[rows, cols]

        img = image[rows, cols, :]
        yield img, current_mask, top_left


def bounding_box(mask):
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    rmin, rmax = np.argmax(rows), mask.shape[0] - np.argmax(np.flipud(rows))
    cmin, cmax = np.argmax(cols), mask.shape[1] - np.argmax(np.flipud(cols))
    return slice(rmin, rmax), slice(cmin, cmax), np.array([rmin, cmin])


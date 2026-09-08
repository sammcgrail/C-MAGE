"""
 * This Software is under the MIT License
 * Refer to LICENSE or https://opensource.org/licenses/MIT for more information
 * Written by ©Kohulan Rajan 2020
"""
import os
import requests
import cv2
import argparse
import warnings
import numpy as np
from copy import deepcopy
from itertools import cycle
from multiprocessing import Pool
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError
from typing import List, Tuple
from PIL import Image
from .complete_structure import complete_structure_mask
from .mrcnn import model as modellib
from .mrcnn import visualize
from .mrcnn import moldetect
#from tensorflow.python.client import device_lib
#device_lib.list_local_devices()
import tensorflow as tf

#CUDA_VISIBLE_DEVICES=0

warnings.filterwarnings("ignore")

# Root directory of the project
ROOT_DIR = os.path.dirname(os.path.dirname(os.getcwd()))


class InferenceConfig(moldetect.MolDetectConfig):
    """
    Inference configuration class for MRCNN
    """

    # Run detection on one image at a time
    GPU_COUNT = 1
    IMAGES_PER_GPU = 1
    DETECTION_MIN_CONFIDENCE = 0.7


def segment_chemical_structures_from_file(
    file_path: str,
    expand: bool = True,
    poppler_path=None,
) -> List[np.array]:
    """
    This function runs the segmentation model as well as the mask expansion
    on a pdf document or an image of a page from a scientific publication.
    It returns a list of segmented chemical structure depictions (np.array)

    Args:
        file_path (str): image of a page from a scientific publication
        expand (bool): indicates whether or not to use mask expansion
        poppler_path: Windows users need to specify the path of their
                        Poppler installation

    Returns:
        List[np.array]: expanded segments (shape: (h, w, num_masks))
    """
    if file_path[-3:].lower() == "pdf":
        try:
            images = convert_from_path(file_path, 300, poppler_path=poppler_path)
        except PDFInfoNotInstalledError:
            poppler_path = "C:\\Program Files (x86)\\poppler-0.68.0\\bin"
            images = convert_from_path(file_path, 300, poppler_path=poppler_path)
        images = [np.array(image) for image in images]
    else:
        images = [cv2.imread(file_path)]
    if len(images) > 1:
        with Pool(4) as pool:
            starmap_args = [(im, expand) for im in images]
            segments = pool.starmap(segment_chemical_structures, starmap_args)
            segments = [su for li in segments for su in li]
    else:
        segments = segment_chemical_structures(images[0])
    return segments


def segment_chemical_structures(
    image: np.array,
    expand: bool = True,
    visualization: bool = False,
) -> List[np.array]:
    """
    This function runs the segmentation model as well as the mask expansion
    -> returns a List of segmented chemical structure depictions (np.array)

    Args:
        image (np.array): image of a page from a scientific publication
        expand (bool): indicates whether or not to use mask expansion
        visualization (bool): indicates whether or not to visualize the
                                results (only works in Jupyter notebook)

    Returns:
        List[np.array]: expanded segments sorted in top->bottom, left->right order with
        a certain tolerance for grouping into "lines"(shape: (h, w, num_masks))
    """
    if not expand:
        masks, bboxes, _ = get_mrcnn_results(image)
    else:
        masks = get_expanded_masks(image)

    segments, bboxes = apply_masks(image, masks)

    if visualization:
        visualize.display_instances(
            image=image,
            masks=masks,
            class_ids=np.array([0] * len(bboxes)),
            boxes=np.array(bboxes),
            class_names=np.array(["structure"] * len(bboxes)),
        )

    if len(segments) > 0:
        segments, bboxes = sort_segments_bboxes(segments, bboxes)

    segments = [segment for segment in segments
                if segment.shape[0] > 0
                if segment.shape[1] > 0]

    return segments


def determine_depiction_size_with_buffer(
    bboxes: List[Tuple[int, int, int, int]]
) -> Tuple[int, int]:
    """
    This function takes a list of bounding boxes and returns 1.1 * the maximal
    depiction size (height, width) of the depicted chemical structures.

    Args:
        bboxes (List[Tuple[int, int, int, int]]): bounding boxes of the structure
            depictions (y0, x0, y1, x1)

    Returns:
        Tuple [int, int]: average depiction size (height, width)
    """
    heights = []
    widths = []
    for bbox in bboxes:
        height = bbox[2] - bbox[0]
        width = bbox[3] - bbox[1]
        heights.append(height)
        widths.append(width)
    height = int(1.1 * np.max(heights))
    width = int(1.1 * np.max(widths))
    return height, width


def sort_segments_bboxes(
    segments: List[np.array],
    bboxes: List[Tuple[int, int, int, int]],  # (y0, x0, y1, x1)
    same_row_pixel_threshold=50,
) -> Tuple[np.array, List[Tuple[int, int, int, int]]]:
    """
    Sorts segments and bounding boxes in "reading order"

    Args:
        segments - image segments to be sorted
        bboxes - bounding boxes containing edge coordinates of the image segments
        same_row_pixel_threshold - how many pixels apart can two pixels be to be
            considered "on the same row"

    Returns:
        segments and bboxes in reading order
    """

    # Sort by y-coordinate (top-to-bottom reading order)
    sorted_bboxes = sorted(bboxes, key=lambda bbox: bbox[0])

    # Group bounding boxes by rows based on y-coordinate
    rows = []
    current_row = [sorted_bboxes[0]]
    for bbox in sorted_bboxes[1:]:
        if (
            abs(bbox[0] - current_row[-1][0]) < same_row_pixel_threshold
        ):  # You can adjust this threshold as needed
            current_row.append(bbox)
        else:
            rows.append(
                sorted(current_row, key=lambda x: x[1])
            )  # Sort by x-coordinate within each row
            current_row = [bbox]
    rows.append(sorted(current_row, key=lambda x: x[1]))  # Sort the last row

    # Flatten the list of rows and return
    sorted_bboxes = [bbox for row in rows for bbox in row]

    sorted_segments = [segments[bboxes.index(bbox)] for bbox in sorted_bboxes]
    return sorted_segments, sorted_bboxes


# Minimum plausible size for the weights. The real file is ~260 MB; anything in
# the kilobytes is an error page, not a model.
_MIN_WEIGHTS_BYTES = 8 * 1024 * 1024
# HDF5 files start with this signature. Checking it is what turns "the server
# sent us something" into "the server sent us a model".
_HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"


def _download_weights(url: str, dest: str) -> None:
    """Fetch the segmentation weights, refusing to cache anything that is not
    an HDF5 file.

    WHY THIS IS NOT `requests.get(url).content` WRITTEN STRAIGHT TO DISK, which
    is what it used to be: on 2026-09-08 Zenodo was down and returned a 92-byte
    HTML error page with HTTP 504. That page was written to
    ~/.cache/decimer/mask_rcnn_molecule.h5, and because the download only runs
    when the file is ABSENT, every later import then failed on the cached
    rubbish with

        OSError: Unable to open file (file signature not found)

    which names neither Zenodo nor the cache. A failed download is a bad
    afternoon; a POISONED CACHE is a bad afternoon that repeats itself and
    points at the wrong thing.

    Four checks, cheapest first, then an atomic rename so a partial or rejected
    download can never be mistaken for a complete cache entry:
      1. HTTP status
      2. content-type is not HTML  (the exact failure that bit us)
      3. the bytes actually start with the HDF5 signature
      4. the file is plausibly large

    Raises RuntimeError naming what arrived and which path to delete.
    """
    tmp = dest + ".part"

    def _fail(what: str) -> None:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise RuntimeError(
            "DECIMER segmentation weights download failed: {}.\n"
            "  url:   {}\n"
            "  cache: {}\n"
            "Nothing was cached, so this will retry cleanly on the next run. "
            "If a bad file predates this check, delete the cache path above."
            .format(what, url, dest)
        )

    try:
        resp = requests.get(url, allow_redirects=True, timeout=60)
    except requests.RequestException as exc:
        _fail("could not reach the server ({})".format(exc))

    if resp.status_code != 200:
        _fail("HTTP {}".format(resp.status_code))

    ctype = resp.headers.get("Content-Type", "")
    if "html" in ctype.lower():
        _fail("server returned an HTML page (Content-Type: {}), not a model. "
              "Zenodo is probably down or rate-limiting".format(ctype))

    body = resp.content
    if not body.startswith(_HDF5_MAGIC):
        _fail("payload is not an HDF5 file (first bytes: {!r})".format(body[:16]))
    if len(body) < _MIN_WEIGHTS_BYTES:
        _fail("payload is only {} bytes; the weights are ~260 MB".format(len(body)))

    with open(tmp, "wb") as fh:
        fh.write(body)
    # Rename last: until this line there is no file at `dest` for a later run
    # to trust.
    os.replace(tmp, dest)


def load_model() -> modellib.MaskRCNN:
    """
    This function loads the segmentation model and returns it. The weights
    are downloaded if necessary.

    Returns:
        modellib.MaskRCNN: MRCNN model with trained weights
    """
    # Cache the weights under ~/.cache, next to where huggingface_hub keeps the
    # other two C-MAGE models. Upstream stores them inside this package, which
    # for an editable install means inside the repository, so re-cloning threw
    # away 260 MB and downloaded it again.
    root_dir = os.path.split(__file__)[0]
    legacy_path = os.path.join(root_dir, "mask_rcnn_molecule.h5")
    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "decimer")
    model_path = os.path.join(cache_dir, "mask_rcnn_molecule.h5")
    # Weights already downloaded to the old location are still used, so nobody
    # who has the file today has to fetch it a second time.
    if os.path.exists(legacy_path):
        model_path = legacy_path
    elif not os.path.exists(model_path):
        os.makedirs(cache_dir, exist_ok=True)
        print("Downloading model weights...")
        url = "https://zenodo.org/record/10663579/files/mask_rcnn_molecule.h5?download=1"
        _download_weights(url, model_path)
        print("Successfully downloaded the segmentation model weights!")
    # Create model object in inference mode.
    #with line is new
    with tf.device("/device:GPU:0"):
   # CUDA_VISIBLE_DEVICES=0
        model = modellib.MaskRCNN(mode="inference", model_dir=".", config=InferenceConfig())
        # Load weights
        model.load_weights(model_path, by_name=True)
    #gpus = tf.device("/device:GPU:0")
    #print("GPUS = " + str(gpus))

    return model


def get_expanded_masks(image: np.array) -> np.array:
    """
    This function runs the segmentation model and returns an
    array with the masks (shape: height, width, num_masks).
    Slicing along the third axis of the output of this function
    yields a binary array of shape (h, w) for a single structure.

    Args:
        image (np.array): image of a page from a scientific publication

    Returns:
        np.array: expanded masks (shape: (h, w, num_masks))
    """
    # Structure detection with MRCNN
    masks, bboxes, _ = get_mrcnn_results(image)
    if len(bboxes) == 0:
        return masks
    size = determine_depiction_size_with_buffer(bboxes)
    # Mask expansion
    expanded_masks = complete_structure_mask(
        image_array=image,
        mask_array=masks,
        max_depiction_size=size,
        debug=False
    )
    return expanded_masks


def get_mrcnn_results(
    image: np.array,
) -> Tuple[np.array, List[Tuple[int]], List[float]]:
    """
    This function runs the segmentation model as well as the mask
    expansion mechanism and returns an array with the masks (shape:
    height, width, num_masks), a list of bounding boxes and a list
    of confidence scores.
    Slicing along the third axis of the mask output of this function
    yields a binary array of shape (h, w) for a single structure.

    Args:
        image (np.array): image of a page from a scientific publication
    Returns:
        np.array: expanded masks (shape: (h, w, num_masks))
        List[Tuple[int]]: bounding boxes [(y0, x0, y1, x1), ...]
        List[float]: confidence scores
    """
    results = model.detect([image], verbose=1)
    scores = results[0]["scores"]
    bboxes = results[0]["rois"]
    masks = results[0]["masks"]
    return masks, bboxes, scores


def apply_masks(image: np.array, masks: np.array) -> List[np.array]:
    """
    This function takes an image and the masks for this image
    (shape: (h, w, num_structures)) and returns a list of segmented
    chemical structure depictions (np.array)

    Args:
        image (np.array): image of a page from a scientific publication
        masks (np.array): masks (shape: (h, w, num_masks))

    Returns:
        List[np.array]: segmented chemical structure depictions
    """
    masks = [masks[:, :, i] for i in range(masks.shape[2])]
    if len(masks) == 0:
        return [], []
    segmented_images_bboxes = map(apply_mask, cycle([image]), masks)
    segmented_images, bboxes = list(zip(*list(segmented_images_bboxes)))
    return segmented_images, bboxes


def apply_mask(image: np.array, mask: np.array) -> np.array:
    """
    This function takes an image and a mask for this image (shape: (h, w))
    and returns a segmented chemical structure depictions (np.array)

    Args:
        image (np.array): image of a page from a scientific publication
        masks (np.array): binary mask (shape: (h, w))

    Returns:
        np.array: segmented chemical structure depiction
        Tuple[int]: (y0, x0, y1, x1)
    """
    # OPT-IN: keep the original pixels inside a padded mask bounding box instead
    # of erasing everything the mask missed.
    #
    # WHY THIS EXISTS. The default path below multiplies by the mask, thresholds,
    # and forces every non-mask pixel to white before cropping. Ink the mask did
    # not cover is therefore ERASED, not merely cropped -- and the segment that
    # reaches stage 3 is a mutilated drawing, inside a crop with clean borders.
    # That is why the resulting wrong molecule scores HIGH confidence: stage 3
    # reads what it was given, faithfully, and cannot know a substituent was
    # deleted. Measured on the repo's own Validation/test_page.pdf, caffeine and
    # paracetamol are both wrong through the default path at 300 dpi AND at 3x
    # upscale (so it is not a resolution problem), and both are recovered by
    # cropping the original pixels at the mask bbox with 15% padding.
    #
    # It is OPT-IN and off by default on purpose: padding can pull in a
    # neighbouring structure's ink on a densely packed figure, which is the very
    # thing masking exists to prevent. Default behaviour is byte-identical to
    # upstream. Turn it on for sparse figures where accuracy matters more:
    #
    #     DECIMER_BBOX_PAD=0.15      # fraction of bbox size, 0 disables
    pad_frac = float(os.environ.get("DECIMER_BBOX_PAD", "0") or 0)
    if pad_frac > 0:
        _, bbox = get_masked_image(deepcopy(image), mask)
        x, y, w, h = bbox
        px, py = int(round(w * pad_frac)), int(round(h * pad_frac))
        H, W = image.shape[:2]
        x0, y0 = max(0, x - px), max(0, y - py)
        x1, y1 = min(W, x + w + px), min(H, y + h + py)
        return image[y0:y1, x0:x1].copy(), (y0, x0, y1, x1)

    # TODO: Further cleanup
    im = deepcopy(image)
    for channel in range(image.shape[2]):
        im[:, :, channel] = im[:, :, channel] * mask
    masked_image, bbox = get_masked_image(deepcopy(image), mask)
    x, y, w, h = bbox
    im_gray = cv2.cvtColor(masked_image, cv2.COLOR_RGB2GRAY)
    _, im_bw = cv2.threshold(im_gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    # Removal of transparent layer and generation of segment
    _, alpha = cv2.threshold(im_bw, 0, 255, cv2.THRESH_BINARY)
    b, g, r = cv2.split(image)
    rgba = [b, g, r, alpha]
    dst = cv2.merge(rgba, 4)
    background = dst[y : y + h, x : x + w]
    trans_mask = background[:, :, 3] == 0
    background[trans_mask] = [255, 255, 255, 255]
    return background, (y, x, y + h, x + w)


def get_masked_image(image: np.array, mask: np.array) -> np.array:
    """
    This function takes an image and a masks for this image
    (shape: (h, w)) and returns the masked image where only the
    masked area is not completely white and a bounding box of the
    segmented object

    Args:
        image (np.array): image of a page from a scientific publication
        mask (np.array): masks (shape: (h, w, num_masks))

    Returns:
        List[np.array]: segmented chemical structure depictions
        List[int]: bounding box of segmented object
    """
    for channel in range(image.shape[2]):
        image[:, :, channel] = image[:, :, channel] * mask[:, :]
    # Remove unwanted background
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresholded = cv2.threshold(grayscale, 0, 255, cv2.THRESH_OTSU)
    bbox = cv2.boundingRect(thresholded)

    masked_image = np.zeros(image.shape).astype(np.uint8)
    masked_image = visualize.apply_mask(masked_image, mask, [1, 1, 1])
    masked_image = Image.fromarray(masked_image)
    masked_image = masked_image.convert("RGB")
    return np.array(masked_image), bbox


def save_images(images: List[np.array], path: str, name: str) -> None:
    """
    This function takes an array of np.array images, an output path
    and an ID for the name generation and saves the images as png files
    ("$name_$index.png).

    Args:
        images (List[np.array]): Images
        path (str): Output directory
        name (str): name for filename generation
    """
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    for index in range(len(images)):
        filename = f"{name}_{index}.png"
        file_path = os.path.join(path, filename)
        cv2.imwrite(file_path, images[index])


def get_bnw_image(image: np.array) -> np.array:
    """
    This function takes an image and returns

    Args:
        image (np.array): input image

    Returns:
        np.array: binarized input image
    """
    grayscale_im = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, im_bw = cv2.threshold(
        grayscale_im, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
    )
    return im_bw


def get_square_image(image: np.array, desired_size: int) -> np.array:
    """
    This function takes an image and resizes it without distortion
    with the result of a square image with an edge length of
    desired_size.

    Args:
        image (np.array): input image
        desired_size (int): desired output image length/height

    Returns:
        np.array: resized output image
    """
    image = Image.fromarray(image)
    old_size = image.size
    grayscale_image = image.convert("L")
    if old_size[0] or old_size[1] != desired_size:
        ratio = float(desired_size) / max(old_size)
        new_size = tuple([int(x * ratio) for x in old_size])
        grayscale_image = grayscale_image.resize(new_size, Image.ANTIALIAS)
    else:
        new_size = old_size
    resized_image = Image.new("L", (desired_size, desired_size), "white")

    resized_image.paste(
        grayscale_image,
        ((desired_size - new_size[0]) // 2, (desired_size - new_size[1]) // 2),
    )
    return np.array(resized_image)


model = load_model()


def main():
    """
    This script takes a file path as an argument (pdf or image), runs DECIMER
    Segmentation on it and saves the segmented structures as PNG images.
    """
    # Handle input arguments
    description = "Segment chemical structures from the scientific literature"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--input", help="Enter the input filename (pdf or image)", required=True
    )
    args = parser.parse_args()
    # Define image path and output path
    input_path = os.path.normpath(args.input)
    # Segment chemical structure depictions
    print("Loading model...")
    print("Segmenting structures...")
    segments = segment_chemical_structures_from_file(input_path)
    # Save segments
    segment_dir = os.path.join(f"{input_path}_output", "segments")
    save_images(segments, segment_dir, os.path.split(input_path)[1][:-4])
    print(f"The segmented images can be found in {segment_dir}")


if __name__ == "__main__":
    main()

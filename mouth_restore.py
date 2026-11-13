import cv2
import numpy as np
import torch
from PIL import Image

from photo_detail import as_float, as_image

WEIGHTS = 'models/gfpgan/GFPGANv1.4.pth'
ALIGNED_SIZE = 512
# These points are the eye centers, the nose tip, and the mouth corners in the 512 pixel face that GFPGAN expects.
ALIGNED_POINTS = np.float32([[192.98138, 239.94708], [318.90277, 240.1936], [256.63416, 314.01935],
                             [201.26117, 371.41043], [313.08905, 371.15118]])
MOUTH_LABELS = (11, 12, 13)
DETAIL_SCALE = 4
SAME_SHAPE_BELOW = 10
OTHER_SHAPE_ABOVE = 25
MOUTH_EDGE_SOFTNESS = 1


def soft(image):
    return cv2.GaussianBlur(as_float(image), (0, 0), DETAIL_SCALE)


def as_batch(image):
    return torch.from_numpy(image[:, :, ::-1].copy()).permute(2, 0, 1).float().div(255).unsqueeze(0).cuda()


def alignment(landmarks):
    """Return the transform that moves a face with these 68 landmarks to the aligned position."""
    points = np.float32([landmarks[36:42].mean(axis=0), landmarks[42:48].mean(axis=0),
                         landmarks[30], landmarks[48], landmarks[54]])
    return cv2.estimateAffinePartial2D(points, ALIGNED_POINTS, method=cv2.LMEDS)[0]


def with_restored_detail(aligned, restored):
    # GFPGAN closes a partially open mouth and makes the lips redder.
    # This function adds only fine detail where GFPGAN kept the shape.
    soft_restored = soft(restored)
    shape_change = cv2.GaussianBlur(np.abs(soft(aligned) - soft_restored).max(axis=2), (0, 0), DETAIL_SCALE)
    same_shape = 1 - np.clip((shape_change - SAME_SHAPE_BELOW) / (OTHER_SHAPE_ABOVE - SAME_SHAPE_BELOW), 0, 1)
    return as_image(aligned + same_shape[..., None] * (restored - soft_restored))


def put_mouth_back(frame, sharp_face, mouth, to_aligned):
    size = frame.shape[1], frame.shape[0]
    cover = cv2.GaussianBlur(mouth.astype(np.float32), (0, 0), MOUTH_EDGE_SOFTNESS)
    cover = cv2.warpAffine(cover, to_aligned, size, flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)[..., None]
    sharp_frame = cv2.warpAffine(sharp_face, to_aligned, size, flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP)
    return as_image(frame * (1 - cover) + sharp_frame * cover)


def mouth_restorer(photo, face_parser):
    """Return a function that sharpens the mouth in each BGR frame.

    The head must stay in the photo position. face_parser is FaceParsing.
    """
    # The upstream modules load their models on import. So only this function imports them.
    import spandrel
    from mmpose.apis import inference_topdown
    from mmpose.structures import merge_data_samples
    from musetalk.utils.preprocessing import model as pose_model

    keypoints = merge_data_samples(inference_topdown(pose_model, photo)).pred_instances.keypoints[0]
    to_aligned = alignment(keypoints[23:91])
    restorer = spandrel.ModelLoader(device='cuda').load_from_file(WEIGHTS).eval()

    @torch.no_grad()
    def restore(frame):
        aligned = cv2.warpAffine(frame, to_aligned, (ALIGNED_SIZE, ALIGNED_SIZE), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REFLECT)
        restored = restorer(as_batch(aligned)).clamp(0, 1)[0].permute(1, 2, 0).mul(255).cpu().numpy()[:, :, ::-1]
        sharp_face = with_restored_detail(aligned, restored)
        parser_input = face_parser.preprocess(Image.fromarray(sharp_face[:, :, ::-1].copy())).unsqueeze(0).cuda()
        labels = face_parser.net(parser_input)[0][0].argmax(0).cpu().numpy()
        return put_mouth_back(frame, sharp_face, np.isin(labels, MOUTH_LABELS), to_aligned)

    return restore

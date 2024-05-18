import hashlib
import json
import logging
import os
from enum import Enum
from typing import Dict, Optional, Tuple

import matplotlib.pyplot as plt
import requests
from pydantic import BaseModel, ConfigDict, Field
from pydantic.fields import PrivateAttr

from frigate.util.builtin import load_labels

logger = logging.getLogger(__name__)


class PixelFormatEnum(str, Enum):
    rgb = "rgb"
    bgr = "bgr"
    yuv = "yuv"


class InputTensorEnum(str, Enum):
    nchw = "nchw"
    nhwc = "nhwc"


class ModelTypeEnum(str, Enum):
    ssd = "ssd"
    yolox = "yolox"
    yolov5 = "yolov5"
    yolov8 = "yolov8"
    yolonas = "yolonas"

class ModelConfig(BaseModel):
    path: Optional[str] = Field(None, title="Custom Object detection model path.")
    labelmap_path: Optional[str] = Field(
        None, title="Label map for custom object detector."
    )
    width: int = Field(default=320, title="Object detection model input width.")
    height: int = Field(default=320, title="Object detection model input height.")
    labelmap: Dict[int, str] = Field(
        default_factory=dict, title="Labelmap customization."
    )
    input_tensor: InputTensorEnum = Field(
        default=InputTensorEnum.nhwc, title="Model Input Tensor Shape"
    )
    input_pixel_format: PixelFormatEnum = Field(
        default=PixelFormatEnum.rgb, title="Model Input Pixel Color Format"
    )
    model_type: ModelTypeEnum = Field(
        default=ModelTypeEnum.ssd, title="Object Detection Model Type"
    )
    _merged_labelmap: Optional[Dict[int, str]] = PrivateAttr()
    _colormap: Dict[int, Tuple[int, int, int]] = PrivateAttr()
    _model_hash: str = PrivateAttr()

    @property
    def merged_labelmap(self) -> Dict[int, str]:
        return self._merged_labelmap

    @property
    def colormap(self) -> Dict[int, Tuple[int, int, int]]:
        return self._colormap

    @property
    def model_hash(self) -> str:
        return self._model_hash

    def __init__(self, **config):
        super().__init__(**config)

        self._merged_labelmap = {
            **load_labels(config.get("labelmap_path", "/labelmap.txt")),
            **config.get("labelmap", {}),
        }
        self._colormap = {}

    def compute_model_hash(self) -> None:
        if not self.path or not os.path.exists(self.path):
            self._model_hash = hashlib.md5(b"unknown").hexdigest()
        else:
            with open(self.path, "rb") as f:
                file_hash = hashlib.md5()
                while chunk := f.read(8192):
                    file_hash.update(chunk)
            self._model_hash = file_hash.hexdigest()

    def create_colormap(self, enabled_labels: set[str]) -> None:
        """Get a list of colors for enabled labels."""
        cmap = plt.cm.get_cmap("tab10", len(enabled_labels))

        for key, val in enumerate(enabled_labels):
            self._colormap[val] = tuple(int(round(255 * c)) for c in cmap(key)[:3])

    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class BaseDetectorConfig(BaseModel):
    # the type field must be defined in all subclasses
    type: str = Field(default="cpu", title="Detector Type")
    model: Optional[ModelConfig] = Field(
        default=None, title="Detector specific model configuration."
    )
    model_config = ConfigDict(
        extra="allow", arbitrary_types_allowed=True, protected_namespaces=()
    )

"""
NII application views
"""
import os
import shutil
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponse, JsonResponse

from backend.applications.nii.model import NIIModel

# Logger
class FakeLogger:
    def info(self, msg, *args, **kwargs):
        print(msg % args if args else msg)

    def debug(self, msg, *args, **kwargs):
        print(msg % args if args else msg)


logger_nii = FakeLogger()

UPLOAD_DIR = Path("/data/root/web/NII")
INPUT_DIR = UPLOAD_DIR / "input"
OUTPUT_DIR = UPLOAD_DIR / "output"
REQUEST_DIR = UPLOAD_DIR / "req"


def generate_request_tempdir():
    """生成请求临时目录"""
    prefix = datetime.now().strftime("%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return REQUEST_DIR / f"{prefix}-{suffix}"


@dataclass
class UploadChunk:
    """上传文件块数据类"""
    request_id: str
    file: UploadedFile
    filename: str
    chunk_id: int
    chunk_total: int
    file_id: int
    file_total: int

    @classmethod
    def from_dict(cls, data: dict, file: UploadedFile):
        converted = {}
        for name, t in cls.__annotations__.items():
            if name != "file":
                converted[name] = t(data[name])
        return cls(**converted, file=file)


class File(NamedTuple):
    """文件信息"""
    total_chunks: int
    recv_chunks: set[int]


class RequestManager:
    """请求管理器"""
    class Request:
        def __init__(self, chunk: UploadChunk):
            self.id = chunk.request_id
            self.recv_files: list[File | None] = [None] * chunk.file_total
            self.recv_filenames = [""] * chunk.file_total
            self.temp_root = generate_request_tempdir()
            self._processing: set[tuple[int, int]] = set()
            self._inst_lock = threading.RLock()
            self._dumped = False

        @property
        def done(self):
            return all(
                f and f.total_chunks == len(f.recv_chunks) for f in self.recv_files
            )

        def get_chunk_path(self, file_id, chunk_id):
            return self.temp_root / f"file-{file_id}" / f"part-{chunk_id}.bin"

        def update(self, chunk: UploadChunk):
            if chunk.file_id >= len(self.recv_files) or chunk.file_id < 0:
                raise ValueError("File id out of range")
            if chunk.request_id != self.id:
                raise ValueError("Request id mismatch")
            if chunk.file_total != len(self.recv_files):
                raise ValueError("File total mismatch")
            curr = self.recv_files[chunk.file_id]
            if curr and chunk.chunk_id in curr.recv_chunks:
                return
            if chunk.chunk_id < 0 or chunk.chunk_id >= chunk.chunk_total:
                raise ValueError("Chunk id out of range")
            with self._inst_lock:
                if (chunk.file_id, chunk.chunk_id) in self._processing:
                    return
                self._processing.add((chunk.file_id, chunk.chunk_id))
            chunk_path = self.get_chunk_path(chunk.file_id, chunk.chunk_id)
            chunk_path.parent.mkdir(parents=True, exist_ok=True)
            with chunk_path.open("wb+") as f:
                for data in chunk.file.chunks():
                    f.write(data)
            with self._inst_lock:
                if self.recv_files[chunk.file_id] is None:
                    self.recv_files[chunk.file_id] = File(
                        chunk.chunk_total, {chunk.chunk_id}
                    )
                    self.recv_filenames[chunk.file_id] = chunk.filename
                else:
                    self.recv_files[chunk.file_id].recv_chunks.add(chunk.chunk_id)

        @property
        def target_dir(self):
            return INPUT_DIR / self.temp_root.name

        def merge_chunks(self):
            with self._inst_lock:
                if self._dumped:
                    return
                self._dumped = True
            assert self.done
            if self.target_dir.exists():
                return
            self.target_dir.mkdir(parents=True)
            for i, (num_chunks, _) in enumerate(self.recv_files):
                out = self.target_dir / (self.recv_filenames[i] or f"file-{i}")
                with out.open("wb") as f:
                    for j in range(num_chunks):
                        chunk_path = self.temp_root / f"file-{i}" / f"part-{j}.bin"
                        with chunk_path.open("rb") as g:
                            shutil.copyfileobj(g, f)
                logger_nii.info(f"Dump req {self.id} File {i + 1} > {out}")
            shutil.rmtree(self.temp_root)

    requests: dict[str, Request] = {}
    requests_out: dict[str, Path] = {}
    _lock = threading.Lock()

    @classmethod
    def update(cls, chunk: UploadChunk) -> Request:
        with cls._lock:
            if chunk.request_id not in cls.requests:
                cls.requests[chunk.request_id] = cls.Request(chunk)
            request_manager = cls.requests[chunk.request_id]
        request_manager.update(chunk)
        return request_manager

    @classmethod
    def abort(cls, request_id):
        with cls._lock:
            if request_id in cls.requests:
                shutil.rmtree(cls.requests[request_id].temp_root, ignore_errors=True)
                del cls.requests[request_id]

    @classmethod
    def set_output_file(cls, request_id: str, output_file: Path):
        with cls._lock:
            if request_id in cls.requests:
                cls.requests_out[request_id] = output_file

    @classmethod
    def get_output_file(cls, request_id: str):
        if request_id in cls.requests_out:
            return cls.requests_out[request_id]
        raise KeyError


def upload_file(request):
    """上传文件（分块）"""
    if request.method == "POST":
        if "file" not in request.FILES:
            return JsonResponse({"msg": "File required"}, status=400)
        try:
            chunk_params = UploadChunk.from_dict(request.POST, request.FILES["file"])
        except KeyError as e:
            key = str(e).removeprefix("KeyError: ")
            return JsonResponse({"msg": f"Param {key} required"}, status=400)
        except ValueError as e:
            return JsonResponse({"msg": f"Expected integer for id/total"}, status=400)
        except Exception as e:
            return JsonResponse({"msg": f"Unexpected: {e}"}, status=500)

        logger_nii.info(
            "Recv req [%s], File %d/%d, Chunk %d/%d",
            chunk_params.request_id,
            chunk_params.file_id + 1,
            chunk_params.file_total,
            chunk_params.chunk_id + 1,
            chunk_params.chunk_total,
        )

        try:
            req_manager = RequestManager.update(chunk_params)
            if req_manager.done:
                req_manager.merge_chunks()
        except Exception as e:
            RequestManager.abort(chunk_params.request_id)
            return JsonResponse({"msg": f"Invalid file/chunk id: {e}"}, status=400)

        return JsonResponse({"msg": "Success"}, status=200)


def infer_file(request):
    """推理文件"""
    if request.method == "POST":
        if "request_id" not in request.POST:
            return JsonResponse({"msg": "Request id required"}, status=400)

        req_id = request.POST["request_id"]
        if req_id not in RequestManager.requests:
            return JsonResponse({"msg": "Invalid request id"}, status=400)

        input_dir = RequestManager.requests[req_id].target_dir
        output_dir = OUTPUT_DIR / input_dir.name
        nii = NIIModel.get_instance(logger_nii)
        c1, c2, angle, out_file = nii.predict(input_dir.name, input_dir, output_dir)

        RequestManager.set_output_file(req_id, out_file)

        return JsonResponse(
            {
                "centroid1": ",".join(map(str, c1)),
                "centroid2": ",".join(map(str, c2)),
                "rotation_angle": angle,
                "combined_file_name": out_file.name,
            }
        )


def process_file(request):
    """处理文件（旧接口，保留兼容性）"""
    if request.method == "POST":
        if "file" not in request.FILES:
            return JsonResponse({})

        nii_file = request.FILES["file"]
        name = nii_file.name

        nii_input_path = "/data/root/web/NII/input"
        nii_output_path = "/data/root/web/NII/output"

        if not os.path.exists(nii_input_path):
            os.makedirs(nii_input_path)

        if not os.path.exists(nii_output_path):
            os.makedirs(nii_output_path)

        nii_file_path_2 = os.path.join(nii_input_path, name)

        with open(nii_file_path_2, "wb+") as destination:
            for chunk in nii_file.chunks():
                destination.write(chunk)

        nii = NIIModel.get_instance(logger_nii)
        result = nii.predict(name, nii_input_path, nii_output_path)

        if os.path.exists(nii_input_path + "/" + name):
            os.remove(nii_input_path + "/" + name)

        if os.path.exists(nii_output_path + "/net_" + name):
            os.remove(nii_output_path + "/net_" + name)

        if os.path.exists(nii_output_path + "/seg_" + name):
            os.remove(nii_output_path + "/seg_" + name)

        combined_file_name = "combine_" + name

        return JsonResponse(
            {
                "centroid1": str(result[0][0]) + "," + str(result[0][1]) + "," + str(result[0][2]),
                "centroid2": str(result[1][0]) + "," + str(result[1][1]) + "," + str(result[1][2]),
                "rotation_angle": result[2],
                "combined_file_name": combined_file_name,
            }
        )


def download_file(request):
    """下载文件"""
    query = request.GET
    if "request_id" not in query:
        return JsonResponse({"msg": "Request id required"}, status=400)

    req_id = query["request_id"]

    if req_id not in RequestManager.requests:
        return JsonResponse({"msg": "Invalid request id"}, status=400)

    output_path = RequestManager.get_output_file(req_id)

    with open(output_path, "rb") as f:
        response = HttpResponse(f.read(), content_type="application/octet-stream")
        response["Content-Disposition"] = (
            f'attachment; filename="{os.path.basename(output_path)}"'
        )
        return response


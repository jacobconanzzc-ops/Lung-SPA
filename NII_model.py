import math
import os
import subprocess
from pathlib import Path

import nibabel as nib
import numpy as np
import SimpleITK as sitk
from scipy.ndimage import center_of_mass


def calculate_weighted_centroid(nii_file, weights) -> tuple[float, float, float]:
    img = nib.load(nii_file)
    data = img.get_fdata()

    # unique_values = np.unique(data)
    # print(" unique_values ", unique_values)
    weight_map = np.zeros_like(data)
    for value, weight in weights.items():
        weight_map[data == value] = weight
    total_weight = np.sum(weight_map)
    if total_weight == 0:
        return None

    weighted_centroid = center_of_mass(weight_map)
    return tuple(map(round, weighted_centroid))


def dcm2nii(dicom_dir_, save_dir_):
    dicom_dir_ = str(dicom_dir_)
    save_dir_ = str(save_dir_)
    if not os.path.exists(save_dir_):
        os.mkdir(save_dir_)

    series_ids = sitk.ImageSeriesReader.GetGDCMSeriesIDs(dicom_dir_)
    for idx_series_ids in range(len(series_ids)):
        series_file_names = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(
            dicom_dir_, series_ids[idx_series_ids]
        )
        series_reader = sitk.ImageSeriesReader()
        series_reader.SetFileNames(series_file_names)
        image = series_reader.Execute()
        # print(f"{idx_series_ids} spacing: {image.GetSpacing()}")

        filename = f"{idx_series_ids:03}.nii"
        save_path = os.path.join(save_dir_, filename)
        sitk.WriteImage(image, save_path)
        return save_path

    raise FileNotFoundError


# 01-网络分割
def run_lungmask(input_file_path: str, output_file_path: str, batchsize: int = 1):
    lungmask_command = [
        "lungmask",
        # 此处lungmask脚本须指定绝对路径！！！否则将找不到脚本！！！
        input_file_path,
        output_file_path,
        "--batchsize",
        str(batchsize),
    ]

    subprocess.run(lungmask_command)


# 02-阈值分割
def process_single_nii(file_path, output_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError
    img = sitk.ReadImage(file_path)
    labed_lab = sitk.GetArrayFromImage(img)
    # print(np.max(labed_lab))
    # print(np.min(labed_lab))
    labed_lab = np.where((labed_lab < -600) | (labed_lab >= 400), 0, labed_lab)
    labed_lab = np.where((labed_lab >= -600) & (labed_lab < -300), 1, labed_lab)
    labed_lab = np.where(
        ((labed_lab >= -300) & (labed_lab < 0)) | ((labed_lab > 2) & (labed_lab < 400)),
        2,
        labed_lab,
    )
    labed_lab = labed_lab.astype(int)
    out = sitk.GetImageFromArray(labed_lab)
    sitk.WriteImage(out, output_path)


# 03-NII合并
def combine_nii(file_path1, file_path2, output_path):
    img1 = sitk.ReadImage(file_path1)
    img2 = sitk.ReadImage(file_path2)
    labed_lab1 = sitk.GetArrayFromImage(img1)
    labed_lab2 = sitk.GetArrayFromImage(img2)

    labed_lab3 = np.zeros_like(labed_lab1)
    labed_lab3 = np.where(
        ((labed_lab1 == 1) | (labed_lab1 == 2)) & (labed_lab2 == 2), 1, labed_lab3
    )
    labed_lab3 = np.where(
        ((labed_lab1 == 1) | (labed_lab1 == 2)) & (labed_lab2 == 1), 2, labed_lab3
    )
    labed_lab3 = labed_lab3.astype(int)
    out = sitk.GetImageFromArray(labed_lab3)
    out = sitk.Cast(out, sitk.sitkInt32)
    # print(out.GetPixelIDTypeAsString())
    sitk.WriteImage(out, output_path)


# 04-角度计算
def calculate_rotation_angle(centroid1, centroid2):
    x1, y1, z1 = centroid1
    x2, y2, z2 = centroid2
    if y1 > y2:
        if x1 > x2:
            angle = 180 - math.degrees(math.atan(abs(y1 - y2) / abs(x1 - x2)))
            return f"病人左转度数为 {angle:.2f} 度"
        elif x1 < x2:
            angle = 180 - math.degrees(math.atan(abs(y1 - y2) / abs(x1 - x2)))
            return f"病人右转度数为 {angle:.2f} 度"
        else:
            return "病人翻转度数为 180 度"
    if y1 == y2:
        if x1 > x2:
            return f"病人左转度数为 90 度"
        elif x1 < x2:
            return f"病人右转度数为 90 度"
        else:
            return "无需旋转"
    if y1 < y2:
        if x1 > x2:
            angle = math.degrees(math.atan(abs(y1 - y2) / abs(x1 - x2)))
            return f"病人左转度数为 {angle:.2f} 度"
        elif x1 < x2:
            angle = math.degrees(math.atan(abs(y1 - y2) / abs(x1 - x2)))
            return f"病人右转度数为 {angle:.2f} 度"
        else:
            return "无需旋转"
    raise Exception  # unreachable


Pt = tuple[float, float, float]


class NII:
    def __init__(self, logger):
        self.logger = logger
        logger.debug("Initialized NII.")

    def predict(
        self, name: str, input_dir: Path, output_dir: Path
    ) -> tuple[Pt, Pt, str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)

        src_files = [f for f in input_dir.iterdir() if f.is_file()]
        if len(src_files) == 0:
            raise Exception(f"No NII/DICOM files found in {input_dir}")
        elif len(src_files) == 1:
            nii_input = src_files[0]
        else:
            # merge dicoms into one single nii
            nii_temp = input_dir / "temp"
            nii_input = dcm2nii(input_dir, nii_temp)
        shortname = src_files[0].name.replace(".dcm", ".nii")

        input_file_path = str(nii_input)
        output_net_path = str(output_dir / ("net_" + shortname))
        output_seg_path = str(output_dir / ("seg_" + shortname))

        # 01 nii网络分割： 输入：***.nii 输出：net_***.nii
        run_lungmask(input_file_path, output_net_path, batchsize=1)

        # 02 nii阈值分割： 输入：***.nii 输出：seg_***.nii
        process_single_nii(input_file_path, output_seg_path)

        combine_output_path = "/data/root/web/NII/combine_" + name + ".nii"
        # 03 nii文件网络分割和阈值分割文件合并：   输入：net_***.nii,seg_***.nii 输出：combine_***.nii
        combine_nii(output_net_path, output_seg_path, output_path=combine_output_path)

        # 04 角度计算和俯卧位通气策略：   输入：combine_***.nii，权重weights1（已指定） 输出：角度1
        # 输入：***.nii，权重weights2（已指定） 输出：角度2
        # 输入：角度1，角度2 输出：旋转角度
        nii_file1 = combine_output_path
        weights1 = {1: 9, 2: 1}
        centroid1 = calculate_weighted_centroid(nii_file1, weights1)
        self.logger.info("%s centroid is %s", name, centroid1)
        nii_file2 = input_file_path
        weights2 = {1: 1, 2: 1}
        centroid2 = calculate_weighted_centroid(nii_file2, weights2)
        self.logger.info("%s centroid is %s", name, centroid2)
        rotation_angle = calculate_rotation_angle(centroid1, centroid2)
        return centroid1, centroid2, rotation_angle, Path(combine_output_path)


if __name__ == "__main__":
    lungmask_command = [
        "D:/Anaconda/Scripts/lungmask.EXE",  # 此处可以使用绝对路径，也可以“lungmask"代替
        "C:/Users/Liuli/Desktop/NII/input/000.nii",
        "C:/Users/Liuli/Desktop/NII/output/net_000.nii",
        "--batchsize",
        "1",
    ]
    subprocess.run(lungmask_command)

    nii_input_path = "C:/Users/Liuli/Desktop/NII/input"
    nii_output_path = "C:/Users/Liuli/Desktop/NII/output"
    name = "000.nii"
    nii = NII()
    print(nii.predict(name, nii_input_path, nii_output_path))

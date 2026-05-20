# 肺部影像分割与体位旋转评估软件 V1.0
# Automated Lung CT Segmentation and Posture Rotation Evaluation Software V1.0

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Django-green.svg)](https://docs.djangoproject.com/)
[![License](https://img.shields.io/badge/license-All%20Rights%20Reserved-red.svg)](#许可证-license)

<p align="center">
  <a href="#中文说明">
    <img src="https://img.shields.io/badge/语言-中文说明-orange?style=for-the-badge" alt="中文">
  </a>
  <a href="#english-description">
    <img src="https://img.shields.io/badge/Language-English-blue?style=for-the-badge" alt="English">
  </a>
</p>

---

## 中文说明

### 1. 软件概述
本软件是一款面向临床医生及医学研究人员的专业化医学影像智能分析工具。基于深度学习技术与医学图像处理算法，能够自动化处理肺部 CT 影像数据，实现肺实质精准分割、病变区域提取及病人体位量化评估。为临床诊疗提供客观、可量化的影像分析依据，显著提升影像分析效率与一致性。

### 2. 核心功能
* **格式转换 (DICOM to NIfTI)：** 自动将上传的 DICOM 序列转换为标准 NIfTI 格式（`XXX.nii`），保留原始仿射矩阵、体素尺寸等空间信息。
* **肺实质自动分割：** 基于 `lungmask` 深度学习模型（U-Net 架构），自动精准识别与提取左右肺实质，处理时间 < 3分钟/例。
* **肺部实变区域提取：** 基于 HU（Hounsfield Unit）阈值规则自动分类组织密度：
  * **正常肺组织：** `< -600 HU`
  * **磨玻璃影 (GGO)：** `-600 HU ~ -300 HU`
  * **实变区域 (Consolidation)：** `-300 HU ~ 400 HU`
* **体位旋转角度评估：** 通过对比加权重心与普通三维空间重心，精密量化患者扫描时的体位倾斜与旋转角度。

### 3. 项目结构
本仓库采用完全扁平化的单级目录设计，只包含以下核心文件：
```text
├── __init__.py       # 模块初始化
├── apps.py           # 应用配置声明
├── model.py          # NIIModel 核心单例封装
├── NII_model.py      # 图像处理、肺分割与体位评估核心算法
├── views.py          # 视图层
└── README.md         # 项目说明文档
```

### 4. 环境准备与安装
请确保系统已安装 Python 3.8+ 以及 CUDA 运行环境（用于加速 `lungmask` 模型推理）。

```bash
# 克隆仓库
git clone https://github.com/jacobconanzzc-ops/Lung-SPA.git
cd Lung-SPA

# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装核心依赖库
pip install numpy nibabel torch torchvision lungmask django
```

### 5. 许可证
**版权所有 (All Rights Reserved)**。本软件代码及相关文档受计算机软件著作权保护。未经著作权人明确授权，严禁任何形式的商业闭源、非法分发或修改演绎。

---

## English Description

### 1. Software Overview
This software is a professional medical image intelligent analysis tool designed for clinicians and medical researchers. Based on deep learning technologies and advanced medical image processing algorithms, it automates the workflow of lung CT image processing, including precise lung parenchyma segmentation, lesion area extraction, and quantitative evaluation of patient posture rotation. It provides objective and quantifiable imaging metrics for clinical diagnosis and treatment, significantly improving the efficiency and consistency of image analysis.

### 2. Key Features
* **Format Conversion (DICOM to NIfTI):** Automatically converts uploaded DICOM sequences into the standard NIfTI format (`XXX.nii`), preserving original spatial metadata such as affine matrices and voxel sizes.
* **Automated Lung Segmentation:** Utilizes the `lungmask` deep learning model (U-Net architecture) to accurately identify and extract left and right lung parenchyma (processing time < 3 minutes per case).
* **Lung Consolidation Extraction:** Automatically classifies tissue densities based on HU (Hounsfield Unit) thresholding rules:
  * **Normal Lung Tissue:** `< -600 HU`
  * **Ground-Glass Opacities (GGO):** `-600 HU ~ -300 HU`
  * **Consolidation Area:** `-300 HU ~ 400 HU`
* **Posture Rotation Assessment:** Quantitatively evaluates patient posture tilt and rotation angle during scanning by comparing the weighted 3D centroid with the standard 3D spatial centroid.

### 3. Project Structure
This repository uses a flat single-level directory structure containing only the following files:
```text
├── __init__.py       # Module initialization
├── apps.py           # Application configuration
├── model.py          # NIIModel singleton wrapper
├── NII_model.py      # Image processing, lung segmentation, and posture evaluation logic
├── views.py          # Views layer
└── README.md         # Project README document
```

### 4. Installation & Setup
Ensure that Python 3.8+ and a CUDA runtime environment are installed on your system for accelerating `lungmask` model inference.

```bash
# Clone the repository
git clone https://github.com/jacobconanzzc-ops/Lung-SPA.git
cd Lung-SPA

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # For Linux/Mac
# venv\Scripts\activate   # For Windows

# Install required packages
pip install numpy nibabel torch torchvision lungmask django
```

### 5. License
**All Rights Reserved**. The source code and related documentation of this software are fully protected under Computer Software Copyright. Any form of commercial close-sourcing, unauthorized distribution, or derivative modification is strictly prohibited without explicit permission from the copyright owners.

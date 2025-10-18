# Cloudreve Python Uploader

[![Python 3.x](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

一个功能强大、逻辑严谨的 Python 脚本，用于将本地文件自动化上传至 [Cloudreve](https://github.com/cloudreve/Cloudreve) 网盘，并能自动获取上传后文件的直链。

## ✨ 主要特性

- **自动化登录**: 通过用户名和密码自动登录，获取并管理会话。
- **智能上传**: 完整封装了 Cloudreve V3 API 的三步上传流程：
    1. 获取上传凭证
    2. 上传文件至后端存储
    3. 向 Cloudreve 确认上传完成
- **多策略适配**: 自动识别并支持多种存储策略，包括：
  - 本地存储
  - OneDrive / SharePoint
  - 其他兼容 S3 的远程存储
- **僵尸会话处理**: 能够自动检测并清理因上次上传中断而产生的“僵尸会话”。
- **获取外链**: 文件上传成功后，能自动在目标目录中查找文件 ID，并获取其下载直链。
- **清晰的日志**: 在执行过程中提供清晰的步骤提示和友好的错误信息。

## ⚙️ 环境要求

- Python 3.8 或更高版本
- `pip` 包管理器

## 🚀 快速开始

### 1. 克隆或下载项目

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

> 如果你没有使用 Git，直接下载 `upload_template.py` 脚本即可。

### 2. 安装依赖

该脚本依赖 `requests` 库来处理网络请求。

```bash
pip install requests
```

或者，创建一个 `requirements.txt` 文件，内容为：

```text
requests
```

然后运行：

```bash
pip install -r requirements.txt
```

### 3. 配置脚本

**（重要）** 为了安全和便捷，请**不要**直接修改脚本中的用户名和密码。建议采用配置文件的方式。

创建一个名为 `config.ini` 的文件，并填入以下内容：

```ini
[cloudreve]
# 你的 Cloudreve 实例 API 地址
url = https://cloudreve.example.com/api/v3
# 你的登录邮箱
username = username@example.com
# 你的登录密码
password = your_password_here

[upload]
# 要上传的本地文件的完整路径
local_file_path = E:/path/to/your/file.txt
# 上传到 Cloudreve 的远程目录（/ 代表根目录）
remote_dir = /test
# （可选）存储策略 ID，如不指定则使用默认策略
# 可通过浏览器开发者工具抓包获取
policy_id = MBu4
```

#### 如何获取存储策略 ID

存储策略 ID 就是 `config.ini` 中的 `policy_id` 一项。

先打开你 Cloudreve 的 Web 端，按下 F12 打开浏览器开发者模式。

选择“网络”（或“Network”）一项。

![image](/images/network.png)

上传一个小文件，这时你会发现“网络”中多了一个 `upload`，打开它，其中 `policy_id` 一项就是存储策略 ID。

![image](/images/policy.png)

图中为 `MBu4`。

### 4. 运行脚本

确保你的 `config.ini` 已经写好了。

一切就绪后，在终端运行：

```bash
python main.py
```

你将会看到类似如下的输出：

```text
正在发送登录请求……
登录成功！欢迎，YourNickName。

[STEP 1/5] 正在为 'file.txt' 请求上传凭证...
✔️ 成功获取上传凭证。

[STEP 2/5] 正在上传文件到存储后端...
检测到 OneDrive/SharePoint 策略...
✔️ 文件成功上传到存储后端。

[STEP 3/5] 正在与 Cloudreve 确认上传结果...
执行 OneDrive 专用确认流程...
✔️ Cloudreve 确认成功！文件已入库。

[STEP 4/5] 正在目标目录 '/test' 中查找文件 'file.txt'...
✔️ 成功获取目录内容。
✔️ 成功找到文件，ID为: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

[STEP 5/5] 正在为文件ID 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' 获取外链...
✔️ 成功获取外链。

=============== SUCCESS ================
✅ 完整自动化流程执行成功！
文件外链: https://cloudreve.example.com/api/v3/file/source/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/file.txt
=======================================
```

### 效果展示

![image](/images/reaction.png)

## 作为库使用

你也可以将 `Uploader` 类导入到你自己的 Python 项目中，作为一个强大的 Cloudreve API 工具库。

```python
from upload_template import Uploader, CloudreveAPIException
import os

try:
    uploader = Uploader(api_url="https://cloudreve.example.com/api/v3")
    uploader.login("your-email", "your-password")

    local_path = "path/to/my_document.pdf"
    remote_dir = "/documents"
    
    # 上传文件
    uploader.uploadFile(local_path, remote_dir)
    print("文件上传成功！")

    # 获取外链
    file_id = uploader.findFileId(remote_dir, os.path.basename(local_path))
    link = uploader.getSourceLink(file_id)
    print(f"文件直链：{link}")

except CloudreveAPIException as e:
    print(f"操作失败: {e}")

```

## 📜 许可证

本项目采用 [MIT License](https://opensource.org/licenses/MIT) 授权。

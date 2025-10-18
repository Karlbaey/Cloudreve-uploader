#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
@Project : Cloudreve-uploader
@File : upload.py
@Author : Jerry N. Karlbaey
@Date : 2025-10-18
@Description : This script can automatically upload files to a Cloudreve-mounted cloud drive and return the file's external link.
@Copyright : (c) 2025 Jerry N. Karlbaey. All rights reserved
"""

import requests
import os
import mimetypes
import configparser
from urllib.parse import quote

class CloudreveAPIException(Exception):
    """自定义异常"""
    pass

class Uploader:
    def __init__(self, url: str) -> None:
        self.URL = url
        self.SESSION = requests.Session()
        self.USERSTATUS = None

    def login(self, usr: str, pwd: str) -> None:
        """
        负责登录到 Cloudreve。

        :param usr: 输入注册账号的邮箱
        :param pwd: 输入对应账号的密码
        """
        login_url = f"{self.URL}/user/session"
        payload = {"userName": usr, "Password": pwd}
        print("正在发送登录请求……")
        try:
            response = self.SESSION.post(login_url, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("code") == 0:
                self.USERSTATUS = data.get("data")
                print(f"登录成功！欢迎，{self.USERSTATUS.get('nickname')}。")
            else:
                raise CloudreveAPIException(f"登录失败: {data.get('msg', '未知API错误')}")
        except requests.exceptions.RequestException as e:
            raise CloudreveAPIException(f"登录请求时发生网络错误: {e}") from e

    def getDirectory(self, dir: str = "/"):
        """
        用来获取特定目录（默认为根目录）下的所有文件，这在后面获取文件外链的步骤中非常关键。

        :param dir: 输入文件夹（例如 /test），默认为根目录
        """
        if not self.USERSTATUS:
            raise CloudreveAPIException("操作失败：请在调用此方法前先执行 login()。")
        
        # 根据 API 文档，路径需要进行 URL Encode
        encoded_path = quote(dir)
        dir_url = f"{self.URL}/directory{encoded_path}" # 注意这里的 URL 构造方式
        
        print(f"\n正在获取目录 '{dir}' 的内容……")
        try:
            response = self.SESSION.get(dir_url)
            response.raise_for_status()
            data = response.json()
            if data.get("code") == 0:
                print("✔️ 成功获取目录内容。")
                return data.get("data", {}).get("objects", [])
            elif data.get("code") == 404:
                 raise CloudreveAPIException(f"获取目录 '{dir}' 失败: 目录不存在 (404)")
            else:
                raise CloudreveAPIException(f"获取目录 '{dir}' 失败: {data.get('msg', '未知API错误')}")
        except requests.exceptions.RequestException as e:
            raise CloudreveAPIException(f"获取目录时发生网络错误: {e}") from e

    def _uploadCredential(self, remote: str, filename: str, filesize: int, mime: str | None, policy_id: str) -> dict:
        """
        从 Cloudreve 获取上传凭证，并处理僵尸会话。
        
        :param remote: 网盘中文件夹的路径，如 /my/pictures
        :param filename: 文件名
        :param filesize: 文件大小
        :param mime: 文件的 MIME 类型
        :param policy_id: 存储桶策略，可通过控制台网络抓包得到
        """
        print(f"\n[STEP 1/5] 正在为 '{filename}' 请求上传凭证...")
        credential_url = f"{self.URL}/file/upload"
        payload = {"path": remote, "size": filesize, "name": filename, "mime_type": mime}
        if policy_id:
            payload["policy_id"] = policy_id
            print(f"使用存储策略: {policy_id}")
        
        # 防止僵尸进程阻断上传
        for attempt in range(2):
            response = self.SESSION.put(credential_url, json=payload)
            response.raise_for_status()
            credential_data = response.json()
            if credential_data.get("code") == 0:
                print("✔️ 成功获取上传凭证。")
                return credential_data['data']
            if attempt == 0 and "Upload session existed" in credential_data.get('msg', ''):
                print("⚠️ 检测到已存在的上传会话，正在尝试自动清理...")
                delete_payload = {"path": remote, "name": filename}
                delete_response = self.SESSION.delete(credential_url, json=delete_payload)
                if delete_response.ok and delete_response.json().get("code") == 0:
                    print("✔️ 旧会话清理成功，将自动重试上传。")
                    continue
                else:
                    raise CloudreveAPIException(f"清理旧上传会话失败: {delete_response.text}")
            else:
                raise CloudreveAPIException(f"获取上传凭证失败: {credential_data.get('msg')}")
        
        raise CloudreveAPIException("获取上传凭证失败，重试后仍然无效。")
    
    def _backend(self, local: str, filename: str, filesize: int, mime: str | None, credential: dict) -> requests.Response:
        """
        这个方法是为了泛用才加的，理论上适用于所有 Cloudreve 挂载的网盘。如果用的是 SharePoint，那么只保留 OneDrive / SharePoint 策略也可以。

        :param local: 本地文件路径，如 E:/path/to/file.txt
        :param filename: 文件名
        :param filesize: 文件大小
        :param mime: 文件的 MIME 类型
        :param credential: API 凭证，用来上传
        """
        print(f"\n[STEP 2/5] 正在上传文件到存储后端...")
        with open(local, 'rb') as f:
            is_onedrive_policy = 'uploadURLs' in credential and credential['uploadURLs']
            is_simple_remote_policy = 'url' in credential
            is_local_policy = 'session_id' in credential and not is_onedrive_policy and not is_simple_remote_policy
            if is_simple_remote_policy:
                print("检测到简单远程存储策略...")
                upload_response = requests.post(credential['url'], data=credential.get('form_data', {}), files={'file': (filename, f, mime)}) # type: ignore
            elif is_onedrive_policy:
                print("检测到 OneDrive/SharePoint 策略...")
                upload_url = credential['uploadURLs'][0]
                headers = {'Content-Range': f'bytes 0-{filesize-1}/{filesize}', 'Content-Length': str(filesize)}
                upload_response = requests.put(upload_url, data=f, headers=headers)
            elif is_local_policy:
                print("检测到本地存储策略...")
                upload_url = f"{self.URL}/file/upload/{credential['session_id']}"
                # 这个得防类型检查，PEP 怎么这么坏😡
                upload_response = self.SESSION.post(upload_url, files={'file': (filename, f, mime)}) # type: ignore
            else:
                raise CloudreveAPIException(f"无法识别的上传模式。凭证内容: {credential}")
            
            upload_response.raise_for_status()
            print("✔️ 文件成功上传到存储后端。")
            return upload_response
        
    def _finalize(self, credential: dict, backend_response: requests.Response) -> None:
        """
        确保上传好的文件能在 Web 端看到。如果不与 Cloudreve 确认上传结果，即使上传成功也没办法看见文件。

        :param credential: API 凭证，用来与 Cloudreve 确认上传结果
        :param backend_response: 确认文件已经上传到网盘中
        """
        print(f"\n[STEP 3/5] 正在与 Cloudreve 确认上传结果...")
        is_onedrive_policy = 'uploadURLs' in credential and credential['uploadURLs']
        is_local_policy = 'session_id' in credential and not is_onedrive_policy
        if is_onedrive_policy:
            print("执行 OneDrive 专用确认流程...")
            session_id = credential.get('sessionID')
            if not session_id:
                raise CloudreveAPIException(f"OneDrive 上传后未找到 sessionID 用于确认。凭证: {credential}")
            
            finalize_url = f"{self.URL}/callback/onedrive/finish/{session_id}"
            finalize_response = self.SESSION.post(finalize_url, json={})
            finalize_response.raise_for_status()
            final_data = finalize_response.json()
            if final_data.get("code") != 0:
                raise CloudreveAPIException(f"Cloudreve OneDrive 确认失败: {final_data.get('msg')}")
        
        elif is_local_policy:
            # 对于本地策略，后端响应本身就是 Cloudreve 的响应
            final_data = backend_response.json()
            if final_data.get("code") != 0:
                raise CloudreveAPIException(f"Cloudreve 本地策略确认失败: {final_data.get('msg')}")
        
        # 简单远程策略，通常在上传到后端后即完成，无需额外确认步骤
        
        print("✔️ Cloudreve 确认成功！文件已入库。")
    
    def uploadFile(self, local: str, remote: str = '/', policy_id: str = "") -> None:
        """
        用于上传的方法，默认上传到根目录。
        因为我的 Cloudreve 用的是 SharePoint 挂载，这就必须用专用 API。

        :param local: 本地文件路径，如 E:/path/to/file.txt
        :param remote: 远程盘中文件夹的路径，如 /my/pictures，默认为根目录
        :param policy_id: 存储桶策略，存储策略 ID 可通过浏览器开发者工具网络分析获得，通常为一个四位字符串（如 Ab4d）
        """
        if not self.USERSTATUS:
            raise CloudreveAPIException("操作失败：请在调用此方法前先执行 login()。")
        if not os.path.exists(local):
            raise FileNotFoundError(f"本地文件未找到: {local}")
        filename = os.path.basename(local)
        filesize = os.path.getsize(local)
        mime, _ = mimetypes.guess_type(local) or ('application/octet-stream', None)
        
        try:
            # 步骤 1: 获取上传凭证
            credential = self._uploadCredential(remote, filename, filesize, mime, policy_id)
            # 步骤 2: 上传文件到后端存储
            backend_response = self._backend(local, filename, filesize, mime, credential)
            # 步骤 3: 与 Cloudreve 确认上传结果
            self._finalize(credential, backend_response)
        except (requests.exceptions.RequestException, KeyError) as e:
            # 统一处理错误
            raise CloudreveAPIException(f"文件 '{filename}' 上传过程中发生错误: {e}") from e

    def findFileId(self, directory_path: str, filename: str) -> str:
        """
        用于查找文件 ID，依赖于上面的方法 getDirectory()

        :param dirctory_path: 待查找的目录，需要自己设置到上面的上传目录
        :param filename: 需要查找的文件
        :return: filename 在 Cloudreve 中的 ID 值
        """
        print(f"\n[STEP 4/5] 正在目标目录 '{directory_path}' 中查找文件 '{filename}'...")
        
        objects_in_dir = self.getDirectory(directory_path)
        
        for obj in objects_in_dir:
            if obj.get('name') == filename and obj.get('type') == 'file':
                file_id = obj.get('id')
                if file_id:
                    print(f"✔️ 成功找到文件，ID为: {file_id}")
                    return file_id
        
        # 如果循环结束还没找到
        raise CloudreveAPIException(f"文件上传后未在目标目录 '{directory_path}' 中找到。可能原因：服务器索引延迟，或上传到了非预期目录。")

    def getSourceLink(self, file_id: str) -> str:
        """
        根据文件 ID 获取文件外链。

        :param file_id: 文件 ID，从 findFileId() 方法得到
        :return: 文件的外链
        """
        if not self.USERSTATUS:
            raise CloudreveAPIException("操作失败：请在调用此方法前先执行 login()。")
        
        source_url = f"{self.URL}/file/source"
        payload = {"items": [file_id]}
        print(f"\n[STEP 5/5] 正在为文件ID '{file_id}' 获取外链...")

        try:
            response = self.SESSION.post(source_url, json=payload)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 0:
                source_data = data.get("data")
                if source_data and len(source_data) > 0:
                    link = source_data[0].get('url')
                    if link:
                        print("✔️ 成功获取外链。")
                        return link
                    else:
                        raise CloudreveAPIException("获取外链成功，但响应中未找到 'url' 字段。")
                else:
                    raise CloudreveAPIException(f"获取外链失败，API未返回任何链接信息。msg: {data.get('msg')}")
            else:
                raise CloudreveAPIException(f"获取外链失败: {data.get('msg')}")

        except requests.exceptions.RequestException as e:
            raise CloudreveAPIException(f"获取外链时发生网络错误: {e}") from e

if __name__ == '__main__':
    try:
        # --- 从配置文件读取配置 ---
        config = configparser.ConfigParser()
        config.read('config.ini', encoding='utf-8')

        # Cloudreve 配置
        api_url = config.get('cloudreve', 'url')
        username = config.get('cloudreve', 'username')
        password = config.get('cloudreve', 'password')

        # 上传任务配置
        local = config.get('upload', 'local')
        remote = config.get('upload', 'remote')
        storage_policy_id = config.get('upload', 'policy_id', fallback="") # fallback 保证 policy_id 是可选的

        # --- 执行上传流程 ---
        file_name_to_find = os.path.basename(local)

        upload = Uploader(api_url) # 建议将 URL 作为初始化参数传入
        
        # [Step 0] 登录
        upload.login(username, password)
        
        # [Step 1-3] 执行上传
        upload.uploadFile(local, remote, storage_policy_id)
        
        # [Step 4] 查找文件ID
        found_id = upload.findFileId(remote, file_name_to_find)
        
        # [Step 5] 获取并打印外链
        final_link = upload.getSourceLink(found_id)
        
        print("\n" + "="*15 + " SUCCESS " + "="*16)
        print("✅ 完整自动化流程执行成功！")
        print(f"文件外链: {final_link}")
        print("="*39)

    except (CloudreveAPIException, FileNotFoundError, requests.exceptions.RequestException, configparser.Error) as e:
        print(f"\n--- ❌ 发生错误 ---")
        print(e)

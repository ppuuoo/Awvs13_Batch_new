import json
import time
import requests

requests.packages.urllib3.disable_warnings()  # 忽略 SSL 证书警告


class AwvsApi:
    """
    Awvs 扫描 API
    """

    @staticmethod
    def usage():
        """
        使用说明
        """
        usage_text = """
        +--------------------------------------------------------------+
        +                                                              +
        +            Awvs Tool for Low configuration VPS               +
        +                                                              +
        +                       By:AdianGg                             +
        +                                                              +
        +                    admin@e-wolf.top                          +
        +                                                              +
        +--------------------------------------------------------------+
        运行方式: 
        python AwvsApi.py 
        """
        print(usage_text)

    def __init__(self):
        """
        初始化 Awvs API
        """
        self.info_color = "\033[32m[INFO]\033[0m"
        self.error_color = "\033[31m[ERROR]\033[0m"

        self.file_name = "target.txt"  # 目标文件
        self.api_host = "https://x.x.x.x:13443/"  # API 地址
        self.api_key = "xxxxx"  # API KEY
        self.scan_mode = "11111111-1111-1111-1111-111111111111"  # 扫描模式
        self.scan_speed = "moderate"  # 扫描速度
        self.max_task = 2  # 最大同时扫描任务数

        self.target_list = []  # 目标列表
        self.target_dict = {}  # 目标 -> ID 映射

        self.headers = {
            'X-Auth': self.api_key,
            'content-type': 'application/json'
        }

        if self.check_connect():
            print(self.info_color + " Awvs API 连接成功")
            self.start()
        else:
            print(self.error_color + " Awvs API 连接失败，请检查！")

    def check_connect(self):
        """
        检查 Awvs API 连接
        """
        api = self.api_host + "api/v1/info"
        try:
            response = requests.get(url=api, headers=self.headers, verify=False)
            return response.status_code == 200
        except Exception as e:
            print(self.error_color + f" 连接异常: {str(e)}")
            return False

    def get_existing_targets(self):
        """
        获取已存在的目标，防止重复导入
        """
        api = self.api_host + "api/v1/targets"
        existing_targets = {}

        try:
            response = requests.get(url=api, headers=self.headers, verify=False)
            if response.status_code == 200:
                for target in response.json().get("targets", []):
                    existing_targets[target["address"]] = target["target_id"]
        except Exception as e:
            print(self.error_color + f" 获取已存在目标失败: {str(e)}")

        return existing_targets

    def get_running_scans(self):
        """
        获取正在运行的扫描，防止重复扫描
        """
        api = self.api_host + "api/v1/scans"
        running_scans = {}

        try:
            response = requests.get(url=api, headers=self.headers, verify=False)
            if response.status_code == 200:
                for scan in response.json().get("scans", []):
                    if scan["current_session"]["status"] in ["processing", "scheduled"]:
                        running_scans[scan["target_id"]] = True
        except Exception as e:
            print(self.error_color + f" 获取正在运行的扫描失败: {str(e)}")

        return running_scans

    def start(self):
        """
        读取目标文件并开始扫描
        """
        print(self.info_color + " 读取目标文件...")
        self.read_target_file()
        print(self.info_color + f" 发现 {len(self.target_list)} 个目标")
        
        existing_targets = self.get_existing_targets()  # 获取已存在的目标
        print(self.info_color + f" 服务器已有 {len(existing_targets)} 个目标")

        for target in self.target_list:
            if target in existing_targets:
                self.target_dict[target] = existing_targets[target]
                print(self.info_color + f" {target} 已存在，跳过添加")
            else:
                self.add_target(target)

        self.scan_target()

    def read_target_file(self):
        """
        读取目标文件
        """
        try:
            with open(self.file_name, 'r') as target_file:
                self.target_list = [line.strip() for line in target_file if line.strip()]
            print(self.info_color + " 目标文件读取成功")
        except Exception as e:
            print(self.error_color + f" 目标文件读取失败: {str(e)}")

    def add_target(self, target):
        """
        添加目标到 Awvs
        """
        data = {
            'address': target,
            'description': 'awvs-auto',
            'criticality': '10'
        }
        api = self.api_host + "api/v1/targets"

        try:
            response = requests.post(url=api, data=json.dumps(data), headers=self.headers, verify=False)
            if response.status_code == 201:
                target_id = response.json().get("target_id")
                self.target_dict[target] = target_id
                print(self.info_color + f" {target} 添加成功")
                self.set_speed(target_id)
            else:
                print(self.error_color + f" {target} 添加失败")
        except Exception as e:
            print(self.error_color + f" {target} 添加异常: {str(e)}")

    def set_speed(self, target_id):
        """
        设置扫描速度
        """
        api = self.api_host + f"api/v1/targets/{target_id}/configuration"
        data = {"scan_speed": self.scan_speed}
        requests.patch(url=api, data=json.dumps(data), headers=self.headers, verify=False)

    def scan_target(self):
        """
        依次扫描目标
        """
        running_scans = self.get_running_scans()
        print(self.info_color + f" 当前有 {len(running_scans)} 个正在扫描")

        target_num = 0
        api = self.api_host + "api/v1/me/stats"

        while target_num < len(self.target_list):
            stats_result = requests.get(url=api, headers=self.headers, verify=False)
            scan_num = stats_result.json().get("scans_running_count", 0)

            if scan_num < self.max_task:
                scan_target = self.target_list[target_num]
                scan_id = self.target_dict.get(scan_target)

                if scan_id in running_scans:
                    print(self.info_color + f" {scan_target} 正在扫描中，跳过")
                else:
                    self.add_scan(scan_target, scan_id)

                target_num += 1

            time.sleep(10)

        print(self.info_color + " 所有扫描任务已启动！")

    def add_scan(self, target, target_id):
        """
        启动扫描
        """
        api = self.api_host + "api/v1/scans"
        data = {
            "target_id": target_id,
            "profile_id": self.scan_mode,
            "schedule": {"disable": False, "start_date": None, "time_sensitive": False}
        }

        response = requests.post(url=api, data=json.dumps(data), headers=self.headers, verify=False)
        if response.status_code == 201:
            print(self.info_color + f" {target} 扫描启动成功")
        else:
            print(self.error_color + f" {target} 扫描启动失败")


if __name__ == "__main__":
    AwvsApi.usage()
    AwvsApi()

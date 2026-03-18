# 心知天气API工具类
import requests
from pydantic import Field
from configs.setting_1 import TIME_OUT, settings


class WeatherCheck:
    # pydantic的Field定义字段，提供描述信息，该信息会在LC框架中生成工具描述
    city: str = Field(description="City name,include city and county")

    def __init__(self, api_key=None):
        self.api_key = api_key or settings.weather_api_key

    def _fetch_weather_data(self, url):
        """内部方法：重试获取天气数据"""
        response = requests.get(url, timeout=TIME_OUT)
        response.raise_for_status()
        return response.json()

    def run(self, city):
        if not city or not isinstance(city, str) or city.strip() == "":
            return "【需要用户输入】请问您想查询哪个城市的天气？不要再调用工具"
        
        city = city.split('\n')[0].strip()  # 清除多余的\n不然 API 会报错。
        if not city:
           return "【需要用户输入】请问您想查询哪个城市的天气？不要再调用工具"
        
        
        if len(city) > 50:
            return "【错误】城市名称过长，请输入50字以内的城市名"

        url = f"https://api.seniverse.com/v3/weather/now.json?key={self.api_key}&location={city}&language=zh-Hans&unit=c"
        
        try:
            data = self._fetch_weather_data(url)

            if 'results' not in data or not data['results']:
                # logger.warning(f"No weather data for city: {city}")
                return f"【查询结果】未找到城市 '{city}' 的天气信息"

            results = data['results'][0]

            weather = results['now'].get('text', '未知')
            temperature = results['now'].get('temperature', '未知')

            return f"【查询结果】{city}的天气是{weather}，温度为{temperature}°C"

        except requests.exceptions.Timeout:
            # logger.error(f"Weather API timeout for city: {city}")
            return f"【查询结果】查询 '{city}' 天气超时，请稍后重试"
        except Exception as e:
            return f"【查询结果】查询天气时出错：{str(e)}"


weather_check = WeatherCheck()
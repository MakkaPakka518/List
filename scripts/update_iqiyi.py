import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re

async def fetch_iqiyi_hot():
    url = "https://www.iqiyi.com/list/tv/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        # 尝试伪装成国内请求，防止被踢到国际版
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                items = []
                seen = set()
                # 暴力提取页面中所有的标题
                for a in soup.find_all('a'):
                    title = a.get('title')
                    if title and len(title) > 1 and "爱奇艺" not in title:
                        clean_title = re.sub(r'第[一二三四五六七八九十百\d]+季', '', title).strip()
                        if clean_title not in seen:
                            seen.add(clean_title)
                            items.append(clean_title)
                
                print(f"抓取到爱奇艺剧名: {items[:10]}...")
        except Exception as e:
            print(f"爱奇艺抓取失败: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_iqiyi_hot())

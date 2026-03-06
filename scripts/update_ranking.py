import urllib.request
import json
import ssl
from bs4 import BeautifulSoup

def fetch_ranking():
    url = "https://colory.mooo.com/bba/ranking"
    
    # SSL 우회 설정 (필요한 경우)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    # Request 헤더 설정 (Cloudflare 우회를 돕기 위한 기본 설정)
    req = urllib.request.Request(
        url, 
        data=None, 
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'
        }
    )

    try:
        response = urllib.request.urlopen(req, context=ctx)
        html = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return

    soup = BeautifulSoup(html, 'lxml')
    rows = soup.select('tbody tr')
    
    data_list = []
    
    for row in rows:
        tds = row.find_all('td')
        if len(tds) < 5:
            continue
            
        # 순위 처리 (이미지인 경우 url 추출, 텍스트인 경우 텍스트 적용)
        rank_html = str(tds[0])
        rank_val = ""
        if 'img' in rank_html:
            img_tag = tds[0].find('img')
            if img_tag and 'src' in img_tag.attrs:
                src = img_tag['src']
                if src.startswith('/'):
                    src = "https://colory.mooo.com" + src
                rank_val = f'<img class="rank-medal" src="{src}" alt="">'
        else:
            rank_val = f'<span class="rank-num">{tds[0].text.strip()}</span>'
            
        branch_name = tds[1].text.strip().replace('키이스케이프 ', '')
        theme_name = tds[2].text.strip()
        rating = tds[3].text.strip()
        
        data_list.append({
            "rankHtml": rank_val,
            "branch": branch_name,
            "theme": theme_name,
            "rating": rating
        })

    # data/ranking.json 에 저장
    with open('data/ranking.json', 'w', encoding='utf-8') as f:
        json.dump(data_list, f, ensure_ascii=False, indent=4)
        print("Success: Generated ranking.json with", len(data_list), "entries.")

if __name__ == '__main__':
    fetch_ranking()

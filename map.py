import os
import json
import requests

# kakao_keys.json에서 API 키 읽기
def load_kakao_keys():
    key_path = os.path.join(os.path.dirname(__file__), "kakao_keys.json")
    if not os.path.exists(key_path):
        raise FileNotFoundError(f"카카오 API 키 파일이 없습니다: {key_path}")
    with open(key_path, "r", encoding="utf-8") as f:
        keys = json.load(f)
    return keys["KAKAO_REST_API_KEY"], keys["KAKAO_JS_KEY"]

KAKAO_REST_API_KEY, KAKAO_JS_KEY = load_kakao_keys()

def get_latlng_from_address(address, kakao_rest_api_key=KAKAO_REST_API_KEY):
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {kakao_rest_api_key}"}
    params = {"query": address}
    response = requests.get(url, headers=headers, params=params)
    result = response.json()
    if result.get('documents'):
        lat = result['documents'][0]['y']
        lng = result['documents'][0]['x']
        return lat, lng
    else:
        return None, None

def get_kakao_map_html(lat, lng, js_key=KAKAO_JS_KEY, width=600, height=400):
    return f"""
    <div id=\"map\" style=\"width:{width}px;height:{height}px;\"></div>
    <script type=\"text/javascript\" src=\"//dapi.kakao.com/v2/maps/sdk.js?appkey={js_key}\"></script>
    <script>
      var mapContainer = document.getElementById('map'),
          mapOption = {{
              center: new kakao.maps.LatLng({lat}, {lng}),
              level: 3
          }};
      var map = new kakao.maps.Map(mapContainer, mapOption);
      var markerPosition  = new kakao.maps.LatLng({lat}, {lng});
      var marker = new kakao.maps.Marker({{
          position: markerPosition
      }});
      marker.setMap(map);
    </script>
    """ 
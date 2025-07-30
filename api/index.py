import os
import json
import time
from collections import defaultdict
from flask import Flask, request, Response
import pygal.maps
import requests
import pycountry

app = Flask(__name__)

# === Конфигурация ===
CACHE_TTL = 3600  # кэш 1 час (в секундах)
CACHE_FILE = "cache.json"

# === Глобальные переменные ===
COUNTRY_CODE_CACHE = {}
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# === Кэш в файле ===
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

cache = load_cache()

# === Получение кода страны ===
def get_country_code(location_string):
    if not location_string:
        return None
    loc_lower = location_string.lower()
    if loc_lower in COUNTRY_CODE_CACHE:
        return COUNTRY_CODE_CACHE[loc_lower]
    try:
        country = pycountry.countries.search_fuzzy(location_string)[0]
        COUNTRY_CODE_CACHE[loc_lower] = country.alpha_2.lower()
        return country.alpha_2.lower()
    except LookupError:
        for country in pycountry.countries:
            if country.name.lower() in loc_lower:
                COUNTRY_CODE_CACHE[loc_lower] = country.alpha_2.lower()
                return country.alpha_2.lower()
    COUNTRY_CODE_CACHE[loc_lower] = None
    return None

# === Получение данных о контрибьюторах с кэшом ===
def get_contributors_with_location(repo_name, token=None):
    now = time.time()
    # Проверка кэша
    if repo_name in cache and now - cache[repo_name]["timestamp"] < CACHE_TTL:
        return cache[repo_name]["data"]

    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    contributors_url = f"https://api.github.com/repos/{repo_name}/contributors"
    resp = requests.get(contributors_url, headers=headers)

    # Фоллбек: если ошибка авторизации или лимит
    if resp.status_code == 401 or resp.status_code == 403:
        print("⚠️ Падение на лимите. Пробуем без токена...")
        resp = requests.get(contributors_url)

    resp.raise_for_status()
    contributors = resp.json()

    users_data = []
    for contributor in contributors:
        user_resp = requests.get(contributor['url'], headers=headers)
        if user_resp.status_code in (401, 403):
            user_resp = requests.get(contributor['url'])  # fallback без токена
        user_resp.raise_for_status()
        user_data = user_resp.json()
        users_data.append({
            "login": user_data.get("login", "").lower(),
            "location": user_data.get("location")
        })

    # Сохраняем в кэш
    cache[repo_name] = {"timestamp": now, "data": users_data}
    save_cache(cache)
    return users_data

# === Маршрут для карты ===
@app.route('/api/map')
def generate_map():
    repo_name = request.args.get('repo')
    if not repo_name or '/' not in repo_name:
        return Response("Ошибка: Укажите параметр 'repo=owner/repo'", status=400)

    # Параметры кастомизации
    title = request.args.get('title', f'Contributors of {repo_name}')
    color = request.args.get('color', '#1f77b4')
    bg = request.args.get('bg', 'white')
    legend = request.args.get('legend', 'true').lower() == 'true'
    width = int(request.args.get('width', 800))
    height = int(request.args.get('height', 500))

    # Токен: пользовательский или серверный
    token = request.args.get('token', GITHUB_TOKEN)

    try:
        contributors = get_contributors_with_location(repo_name, token)
        country_counts = defaultdict(int)

        for user in contributors:
            code = get_country_code(user['location'])
            if code:
                country_counts[code] += 1

        # Рендер карты
        style = pygal.style.Style(
            background=bg,
            plot_background=bg,
            foreground=color,
            foreground_strong=color,
            foreground_subtle=color,
            opacity='.8',
            opacity_hover='.9',
            colors=(color,)
        )
        worldmap_chart = pygal.maps.world.World(style=style, width=width, height=height, show_legend=legend)
        worldmap_chart.title = title
        worldmap_chart.add('Contributors', dict(country_counts))

        svg_image = worldmap_chart.render()
        return Response(svg_image, mimetype='image/svg+xml', headers={'Cache-Control': 'no-cache, max-age=0'})

    except Exception as e:
        return Response(f"Внутренняя ошибка: {e}", status=500)

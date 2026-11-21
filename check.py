import json, os, re, sys, time
import requests
from bs4 import BeautifulSoup

LIST_URL = "https://www.ss.com/lv/transport/cars/bmw/3-series/"
BASE = "https://www.ss.com"
MAX_YEAR = 2004
SEEN_FILE = "seen.json"
TOPIC = os.environ["NTFY_TOPIC"]
HEADERS = {"User-Agent": "Mozilla/5.0 (personal new-listing alert)"}
AD_RE = re.compile(r"^/msg/lv/transport/cars/bmw/[^/]+/[a-z0-9]+\.html$")


def get(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text


def ad_links():
    soup = BeautifulSoup(get(LIST_URL), "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].replace(BASE, "")
        if AD_RE.match(href) and href not in links:
            links.append(href)
    return links


def ad_fields(html):
    soup = BeautifulSoup(html, "html.parser")
    fields = {}
    for td in soup.find_all("td"):
        label = td.get_text(" ", strip=True)
        if label.endswith(":") and len(label) < 40:
            val = td.find_next_sibling("td")
            if val:
                fields.setdefault(label.rstrip(":").strip().lower(), val.get_text(" ", strip=True))
    title = soup.title.get_text(strip=True).replace("SS.COM ", "") if soup.title else ""
    return fields, title


def field(fields, prefix):
    return " ".join(v for k, v in fields.items() if k.startswith(prefix))


def details(fields):
    year = re.search(r"\d{4}", field(fields, "izlaiduma gads"))
    price = re.search(r"\d[\d\s]*€", field(fields, "cena"))
    return {
        "year": int(year.group()) if year else None,
        "engine": field(fields, "dzinēj"),
        "gearbox": field(fields, "ātrumkārba"),
        "mileage": field(fields, "nobraukums"),
        "price": price.group() if price else "",
    }


def matches(d):
    return (
        d["year"] is not None
        and d["year"] <= MAX_YEAR
        and "benzīns" in d["engine"].lower()
        and "manuāl" in d["gearbox"].lower()
    )


def notify(title, message, url=None):
    payload = {"topic": TOPIC, "title": title, "message": message, "tags": ["car"]}
    if url:
        payload["click"] = url
    requests.post("https://ntfy.sh/", json=payload, timeout=30).raise_for_status()


def main():
    first_run = not os.path.exists(SEEN_FILE)
    seen = [] if first_run else json.load(open(SEEN_FILE))
    links = ad_links()
    if not links:
        sys.exit("No ads found on listing page")
    for href in [l for l in links if l not in seen]:
        if not first_run:
            url = BASE + href
            try:
                d = details(ad_fields(get(url))[0])
            except Exception as e:
                print(f"skip {url}: {e}")
                continue
            if matches(d):
                notify(
                    f"BMW 3 · {d['year']} · {d['price']}",
                    f"{d['engine']} · {d['gearbox']} · {d['mileage']} km",
                    url,
                )
                print(f"match {url}")
            time.sleep(2)
        seen.append(href)
    if first_run:
        notify("ss.lv watcher started", f"{len(links)} current BMW 3 ads indexed; alerts only for new ones")
    json.dump(seen[-500:], open(SEEN_FILE, "w"))


if __name__ == "__main__":
    main()

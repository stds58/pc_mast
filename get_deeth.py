import time
import re
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import wikipediaapi
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# === CONFIGURATION ===
WIKI_DEATHS_URL = "https://en.wikipedia.org/wiki/Deaths_in_August_2023"
SEEN_FILE = "seen_deaths.txt"
EMAIL_TO = "your_email@example.com"  # измените
CHECK_INTERVAL = 3600  # 1 час
HEADERS = {'User-Agent': 'WikiDeathNotifier/1.0'}
WIKI = wikipediaapi.Wikipedia(
    user_agent='WikiDeathNotifier/1.0',
    language='en'
)

# Настройки SMTP (пример для Gmail)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_FROM = "your_bot@gmail.com"    # измените
EMAIL_PASSWORD = "your_app_password" # используйте App Password


def extract_all_names_from_page(url: str) -> list[str]:
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Находим корневой контейнер текста статьи
    content = soup.select_one("#mw-content-text .mw-parser-output")
    if not content:
        raise Exception("Контейнер не найден")

    names = []
    # Находим все <ul>, которые находятся непосредственно внутри контейнера
    for ul in content.find_all("ul", recursive=False):
        # Исключаем списки сносок и навбоксы:
        if ul.find_parent("ol") or ul.find_parent(class_="navbox"):
            continue
        # Берём только прямые <li> внутри <ul>
        for li in ul.find_all("li", recursive=False):
            a = li.find("a", href=True, title=True)
            if a and a["href"].startswith("/wiki/") and ":" not in a["title"]:
                names.append(a["title"])

    return names


def get_best_page_and_intro(name: str):
    en_page = WIKI.page(name)
    if not en_page.exists():
        return f"https://en.wikipedia.org/wiki/{name.replace(' ', '_')}", f"Статья не найдена: {name}"

    # Пытаемся найти русскую версию
    langlinks = en_page.langlinks
    if 'ru' in langlinks:
        ru_page = langlinks['ru']
        return ru_page.fullurl, ru_page.summary
    else:
        return en_page.fullurl, en_page.summary


def send_email(subject: str, body: str):
    if not EMAIL_TO or not EMAIL_FROM or not EMAIL_PASSWORD:
        print("[!] Email не настроен — пропускаем отправку")
        print(f"Subject: {subject}\nBody:\n{body}\n")
        return

    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)


def load_seen() -> set:
    if Path(SEEN_FILE).exists():
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for name in seen:
            f.write(name + "\n")


def main():
    seen = load_seen()
    print("Скрипт запущен. Проверка каждые", CHECK_INTERVAL, "секунд.")
    while True:
        try:
            current_names = extract_all_names_from_page(WIKI_DEATHS_URL)
            new_names = [n for n in current_names if n not in seen]

            for name in new_names:
                print(f"Новое имя: {name}")
                try:
                    url, intro = get_best_page_and_intro(name)
                    # Обрежем до первого предложения
                    match = re.search(r'^(.*?[.!?])', intro)
                    intro = match.group(1) if match else intro.split('\n')[0]
                    body = f"{intro}\n\nСсылка: {url}"
                    #send_email(f"Новое имя в списке умерших: {name}", body)
                    print(f"Новое имя в списке умерших: {name}", body)
                    seen.add(name)
                    save_seen(seen)
                except Exception as e:
                    print(f"[!] Ошибка при обработке {name}: {e}")

            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("\nПрервано пользователем.")
            break
        except Exception as e:
            print(f"[!] Ошибка при проверке: {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()

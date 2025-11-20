from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import csv
from collections import Counter
from typing import List, Dict
import random

app = FastAPI(title="Icadus API v3.0", version="3.0.0")
DB_FILE = "global_movie_db.csv"

# --- MODEL ---
class FeedInput(BaseModel):
    # Örn: {"Matrix": 5, "Barbie": 1}
    rated_movies: Dict[str, int] 
    viewed_ids: List[str]

def load_database():
    movies = []
    try:
        with open(DB_FILE, mode='r', encoding='utf-8') as f:
            movies = list(csv.DictReader(f))
        return movies
    except FileNotFoundError:
        return []

db_movies = load_database()

@app.get("/")
def home(): return {"msg": "Icadus 3.0 Ready"}

@app.get("/search")
def search_movie(query: str):
    results = []
    for m in db_movies:
        if query.lower() in m['Title'].lower():
            results.append({"title": m['Title'], "year": m['Year'], "id": m['TMDb ID']})
    return results[:10]

@app.post("/next_batch")
def get_next_batch(data: FeedInput):
    # 1. KULLANICI PROFİLİNİ OLUŞTUR (Ağırlıklı)
    profile = Counter()
    positive_votes_count = 0
    
    for title, score in data.rated_movies.items():
        movie = next((m for m in db_movies if m['Title'] == title), None)
        if movie:
            # Puanlama Mantığı:
            # 5 Puan -> +3 Ağırlık (Çok Seviyor)
            # 4 Puan -> +1 Ağırlık (Seviyor)
            # 3 Puan -> 0 (Nötr)
            # 2 Puan -> -1 (Sevmiyor)
            # 1 Puan -> -3 (Nefret Ediyor - Cezalandır)
            weight = 0
            if score == 5: weight = 3
            elif score == 4: weight = 1
            elif score == 2: weight = -1
            elif score == 1: weight = -3
            
            if score >= 4: positive_votes_count += 1

            for tag in movie['Deep Tags'].split(','):
                profile[tag.strip()] += weight

    # 2. KANAAT GETİRME (CALIBRATION CHECK)
    # Kullanıcı en az 5 filme yüksek puan (4-5) verdiyse algoritma kendine güvenir.
    is_calibrated = positive_votes_count >= 5

    # 3. ADAYLARI PUANLA
    recommendations = []
    for m in db_movies:
        # TEKRAR YOK: Daha önce görülenleri kesinlikle ele
        if m['TMDb ID'] in data.viewed_ids: continue
        
        # Eğer profilde veri yoksa rastgele puan ata (Keşif modu)
        if not profile:
            final_score = random.randint(1, 50)
        else:
            movie_tags = [t.strip() for t in m['Deep Tags'].split(',')]
            
            # Etiket uyumunu hesapla
            match_score = sum([profile[t] for t in movie_tags if t in profile])
            
            # Normalizasyon (Skoru 0-100 arasına yay)
            # Basit bir sigmoid benzeri mantık
            final_score = max(0, min(100, match_score * 5))

        recommendations.append({
            "id": m['TMDb ID'],
            "title": m['Title'],
            "year": m['Year'],
            "score": final_score,
            "overview": m['Overview'],
            "poster_url": m.get('Poster URL', ''),
            "reason": "Based on your DNA"
        })

    # 4. SIRALAMA STRATEJİSİ
    if is_calibrated:
        # Kanaat oluştuysa: EN YÜKSEK PUANLIYI getir (Risk alma)
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        # En tepedeki 5 taneyi al
        final_batch = recommendations[:5]
    else:
        # Kanaat oluşmadıysa: KARIŞIK getir (Farklı türleri dene ki öğrensin)
        # Biraz yüksek puanlı, biraz rastgele
        top_recs = sorted(recommendations, key=lambda x: x['score'], reverse=True)[:50]
        final_batch = random.sample(top_recs, min(5, len(top_recs)))

    return {
        "is_calibrated": is_calibrated, # Mobil uygulama bunu dinleyecek
        "movies": final_batch
    }
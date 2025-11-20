from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import csv
from collections import Counter
from typing import List, Optional
import random

app = FastAPI(title="Icadus API v2.1", version="2.1.0")
DB_FILE = "global_movie_db.csv"

# --- MODEL ---
class FeedInput(BaseModel):
    seed_movies: List[str]       # Elle arayıp eklenenler
    rated_movies: List[str]      # Akışta beğenilenler (4-5 Puan)
    disliked_movies: List[str]   # Beğenilmeyenler (1-2 Puan)
    viewed_ids: List[str]        # Görüntülenen ID'ler

def load_database():
    movies = []
    try:
        with open(DB_FILE, mode='r', encoding='utf-8') as f:
            movies = list(csv.DictReader(f))
        return movies
    except FileNotFoundError:
        return []

db_movies = load_database()

# --- YARDIMCI FONKSİYONLAR ---
def calculate_match_percentage(movie_tags, user_profile):
    """
    Skoru 0-100 arası bir yüzdeye çevirir.
    """
    if not user_profile: return 0 # Profil yoksa 0
    
    match_score = 0
    total_possible = sum(user_profile.values()) # Profildeki toplam ağırlık
    
    matched_tags = []
    for tag in movie_tags:
        if tag in user_profile:
            weight = user_profile[tag]
            match_score += weight
            matched_tags.append(tag)
            
    # Matematiksel Normalizasyon (Logaritmik büyüme yerine lineer yaklaşım)
    # Eğer kullanıcının sevdiği etiketlerin %30'u bu filmde varsa, bu %80+ bir uyumdur.
    if total_possible == 0: return 0
    
    raw_percentage = (match_score / total_possible) * 100
    
    # Boost (Puanı biraz şişiriyoruz ki kullanıcı motive olsun)
    final_percentage = min(98, raw_percentage * 3.5) 
    
    return int(final_percentage), matched_tags

@app.get("/")
def home():
    return {"message": "Icadus Brain 2.1 is Active 🧠"}

@app.get("/search")
def search_movie(query: str):
    results = []
    for m in db_movies:
        if query.lower() in m['Title'].lower():
            results.append({"title": m['Title'], "year": m['Year'], "id": m['TMDb ID']})
    return results[:10]

@app.post("/next_batch")
def get_next_batch(data: FeedInput):
    # 1. KULLANICI PROFİLİ (SÜREKLİ GÜNCELLENEN KİMLİK)
    # Son beğenilenlerin ağırlığı daha fazla olsun (x2)
    profile = Counter()
    
    # Elle seçilenler
    for title in data.seed_movies:
        movie = next((m for m in db_movies if m['Title'] == title), None)
        if movie:
            for tag in movie['Deep Tags'].split(','): profile[tag.strip()] += 1
            
    # Akışta beğenilenler (Daha değerli)
    for title in data.rated_movies:
        movie = next((m for m in db_movies if m['Title'] == title), None)
        if movie:
            for tag in movie['Deep Tags'].split(','): profile[tag.strip()] += 2 # x2 Ağırlık

    # 2. SOĞUK BAŞLANGIÇ (HİÇ VERİ YOKSA)
    if not profile:
        # Rastgele ama kaliteli 5 film getir (Mix)
        candidates = [m for m in db_movies if m['TMDb ID'] not in data.viewed_ids]
        selected = random.sample(candidates, min(5, len(candidates)))
        
        response_list = []
        for m in selected:
            response_list.append({
                "id": m['TMDb ID'],
                "title": m['Title'],
                "year": m['Year'],
                "score": 0, # Profil yoksa skor yok
                "overview": m['Overview'],
                "poster_url": m.get('Poster URL', ''),
                "reason": "Start rating to build your DNA!"
            })
        return response_list

    # 3. ADAYLARI PUANLA (PROFİL VARSA)
    recommendations = []
    for m in db_movies:
        if m['TMDb ID'] in data.viewed_ids: continue
        if m['Title'] in data.disliked_movies: continue # Sevmediği filmleri ele
        
        movie_tags = [t.strip() for t in m['Deep Tags'].split(',')]
        
        score, matched_tags = calculate_match_percentage(movie_tags, profile)
        
        if score > 0:
            recommendations.append({
                "id": m['TMDb ID'],
                "title": m['Title'],
                "year": m['Year'],
                "score": score,
                "overview": m['Overview'],
                "poster_url": m.get('Poster URL', ''),
                "reason": f"Matches: {', '.join(matched_tags[:2])}"
            })

    # Skora göre sırala ama araya biraz sürpriz (serendipity) kat
    recommendations.sort(key=lambda x: x['score'], reverse=True)
    
    # En iyi 20 taneden 5 tane seç (Sürekli aynıları dönmesin)
    top_pool = recommendations[:20]
    random.shuffle(top_pool)
    
    return top_pool[:5]
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import csv
from collections import Counter
from typing import List, Optional
import random

app = FastAPI(title="Icadus MoodCinema API", version="2.0.0")
DB_FILE = "global_movie_db.csv"

# --- MOOD MAP ---
MOOD_MAP = {
    "melankolik": ["Existential", "Loneliness", "Melancholy", "Sad", "Slow Burn", "Philosophical", "Depressing", "Intimate"],
    "eglenceli": ["Comedy", "Satire", "Humor", "Fun", "Adventure", "Fast Paced", "Witty", "Lighthearted"],
    "gerilim": ["Thriller", "Horror", "Suspense", "Dark", "Crime", "Visceral", "Disturbing", "Mystery"],
    "ilham": ["Hope", "Inspiring", "Redemption", "Human Spirit", "Touching", "Biographical", "Success"]
}

# --- MODEL ---
class FeedInput(BaseModel):
    seed_movies: List[str]       # Başlangıçta seçilen 5 film
    rated_movies: List[str]      # Akışta beğenilen (4-5 puan) filmler
    viewed_ids: List[str]        # Daha önce gösterilenlerin ID'si (Tekrar etmesin)
    mood: str

def load_database():
    movies = []
    try:
        with open(DB_FILE, mode='r', encoding='utf-8') as f:
            movies = list(csv.DictReader(f))
        return movies
    except FileNotFoundError:
        return []

db_movies = load_database()

@app.get("/search")
def search_movie(query: str):
    results = []
    for m in db_movies:
        if query.lower() in m['Title'].lower():
            results.append({"title": m['Title'], "year": m['Year'], "id": m['TMDb ID']})
    return results[:10]

@app.post("/next_batch")
def get_next_batch(data: FeedInput):
    """Sonsuz akış için sıradaki 5 filmi getirir."""
    
    # 1. KULLANICI PROFİLİNİ OLUŞTUR (Başlangıç + Son Beğenilenler)
    active_list = data.seed_movies + data.rated_movies
    active_movies = [m for m in db_movies if m['Title'] in active_list]
    
    profile = Counter()
    for m in active_movies:
        tags = m['Deep Tags'].split(',')
        for tag in tags:
            profile[tag.strip()] += 1

    target_tags = MOOD_MAP.get(data.mood.lower(), [])
    
    # 2. ADAYLARI PUANLA
    recommendations = []
    
    for m in db_movies:
        # Daha önce izlendiyse atla
        if m['TMDb ID'] in data.viewed_ids: continue
        
        movie_tags = [t.strip() for t in m['Deep Tags'].split(',')]
        
        # A. Profil Uyumu
        profile_score = sum([profile[t] for t in movie_tags if t in profile])
        
        # B. Mood Uyumu (Çok Önemli)
        mood_score = sum([10 for t in movie_tags if any(mt in t for mt in target_tags)])
        
        final_score = (profile_score * 2) + mood_score
        
        if final_score > 0:
            # Neden önerildi?
            matched = [t for t in movie_tags if t in profile]
            reason = f"Tags: {', '.join(matched[:2])}"
            
            recommendations.append({
                "id": m['TMDb ID'],
                "title": m['Title'],
                "year": m['Year'],
                "score": final_score,
                "overview": m['Overview'],
                "poster_url": m.get('Poster URL', ''),
                "reason": reason
            })

    # 3. SIRALA VE KARIŞTIR (Hep aynılar gelmesin diye biraz randomness)
    recommendations.sort(key=lambda x: x['score'], reverse=True)
    
    # En iyi 50 tanesinden rastgele 5 tane seç (Çeşitlilik için)
    top_pool = recommendations[:50]
    random.shuffle(top_pool)
    
    return top_pool[:5]
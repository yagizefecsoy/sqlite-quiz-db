"""
SQLite Quiz Veri Tabanı - Örnek veri üretme betiği

Yaptıkları (sırasıyla):
  1. quiz.db dosyasını silip schema.sql ile sıfırdan kurar
  2. 1 hoca + 60 öğrenci ekler (şifreler hash + salt ile saklanır)
  3. 5 oturum ekler
  4. sorular.csv dosyasındaki 100 soruyu ekler ve oturumlara 20'şer bağlar
  5. Oturumları oynatır: 3'ü bitmiş, 1'i sürüyor, 1'i başlamamış
  6. Kayıt sayılarını ekrana yazar

Çalıştırma:  python seed.py
"""

import csv
import hashlib
import os
import random
import sqlite3
from datetime import datetime, timedelta

VERITABANI = "quiz.db"
OGRENCI_SAYISI = 60
SORU_SAYISI_OTURUM_BASINA = 20

# Aynı "rastgele" veri her çalıştırmada tekrar üretilsin diye sabit tohum.
random.seed(42)

ADLAR = ["Ahmet", "Ayşe", "Mehmet", "Fatma", "Ali", "Zeynep", "Mustafa", "Elif",
         "Emre", "Merve", "Burak", "Esra", "Can", "Selin", "Mert", "Büşra",
         "Kerem", "Ece", "Onur", "Deniz", "Yusuf", "İrem", "Hakan", "Gizem",
         "Serkan", "Damla", "Oğuz", "Melis", "Tolga", "Nehir"]

SOYADLAR = ["Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Yıldız", "Yıldırım",
            "Öztürk", "Aydın", "Özdemir", "Arslan", "Doğan", "Kılıç", "Aslan",
            "Çetin", "Kara", "Koç", "Kurt", "Özkan", "Şimşek", "Polat", "Erdem"]

# Arayüzde giriş yapabilmek için örnek (deneme) şifreler.
OGRENCI_SIFRESI = "ogrenci123"
HOCA_SIFRESI = "hoca123"


def sifre_hashle(sifre):
    """Şifreyi rastgele bir salt ile PBKDF2-SHA256'dan geçirir.
    Geriye (hash, salt) döner; ikisi de metin (hex) olarak saklanır."""
    salt = os.urandom(16)
    ozet = hashlib.pbkdf2_hmac("sha256", sifre.encode("utf-8"), salt, 100_000)
    return ozet.hex(), salt.hex()


def zaman_metni(zaman):
    """datetime nesnesini SQLite'ın kullandığı 'YYYY-AA-GG SS:DD:ss' biçimine çevirir."""
    return zaman.strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------
# 1) Veritabanını sıfırdan kur
# ---------------------------------------------------------------------
if os.path.exists(VERITABANI):
    os.remove(VERITABANI)

baglanti = sqlite3.connect(VERITABANI)
baglanti.execute("PRAGMA foreign_keys = ON;")

with open("schema.sql", encoding="utf-8") as dosya:
    baglanti.executescript(dosya.read())


# ---------------------------------------------------------------------
# 2) Kullanıcılar: 1 hoca + 60 öğrenci
# ---------------------------------------------------------------------
sifre_hash, sifre_salt = sifre_hashle(HOCA_SIFRESI)
baglanti.execute(
    """INSERT INTO kullanicilar (ogrenci_no, ad, soyad, email, sifre_hash, sifre_salt, rol, kayit_zamani)
       VALUES (NULL, 'Ders', 'Hocası', 'hoca@okul.edu.tr', ?, ?, 'hoca', '2026-09-01 09:00:00')""",
    (sifre_hash, sifre_salt),
)

ogrenci_idleri = []
for i in range(1, OGRENCI_SAYISI + 1):
    ogrenci_no = f"2024{i:04d}"                      # 20240001, 20240002, ...
    email = f"{ogrenci_no}@ogrenci.edu.tr"
    ad = random.choice(ADLAR)
    soyad = random.choice(SOYADLAR)
    sifre_hash, sifre_salt = sifre_hashle(OGRENCI_SIFRESI)

    # Kayıt zamanı: Eylül'ün ilk üç haftası içinde rastgele bir an
    kayit = datetime(2026, 9, 1, 8, 0, 0) + timedelta(minutes=random.randint(0, 20 * 24 * 60))

    imlec = baglanti.execute(
        """INSERT INTO kullanicilar (ogrenci_no, ad, soyad, email, sifre_hash, sifre_salt, rol, kayit_zamani)
           VALUES (?, ?, ?, ?, ?, ?, 'ogrenci', ?)""",
        (ogrenci_no, ad, soyad, email, sifre_hash, sifre_salt, zaman_metni(kayit)),
    )
    ogrenci_idleri.append(imlec.lastrowid)          # yeni eklenen satırın id'si


# ---------------------------------------------------------------------
# 3) Oturumlar: hepsi önce 'baslamadi' durumunda eklenir
# ---------------------------------------------------------------------
OTURUMLAR = [
    # (kod,      başlık,                 hafta)
    ("w01-s01", "Week 1 · Session 1", 1),
    ("w01-s02", "Week 1 · Session 2", 1),
    ("w01-s03", "Week 1 · Session 3", 1),
    ("w02-s01", "Week 2 · Session 1", 2),
    ("w02-s02", "Week 2 · Session 2", 2),
]

oturum_idleri = []
for kod, baslik, hafta in OTURUMLAR:
    imlec = baglanti.execute(
        "INSERT INTO oturumlar (kod, baslik, hafta) VALUES (?, ?, ?)",
        (kod, baslik, hafta),
    )
    oturum_idleri.append(imlec.lastrowid)


# ---------------------------------------------------------------------
# 4) Sorular: CSV'den okunur, sırayla 20'şer 20'şer oturumlara bağlanır
#    (1-20. sorular 1. oturuma, 21-40. sorular 2. oturuma, ...)
# ---------------------------------------------------------------------
with open("sorular.csv", encoding="utf-8") as dosya:
    sorular = list(csv.DictReader(dosya))

for sira_no, soru in enumerate(sorular):
    imlec = baglanti.execute(
        """INSERT INTO sorular (metin, secenek_a, secenek_b, secenek_c, secenek_d, dogru_cevap, konu)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (soru["metin"], soru["secenek_a"], soru["secenek_b"], soru["secenek_c"],
         soru["secenek_d"], soru["dogru_cevap"], soru["konu"]),
    )
    soru_id = imlec.lastrowid

    oturum_id = oturum_idleri[sira_no // SORU_SAYISI_OTURUM_BASINA]  # 0-19 -> 1. oturum ...
    sira = sira_no % SORU_SAYISI_OTURUM_BASINA + 1                    # oturum içinde 1..20
    baglanti.execute(
        "INSERT INTO oturum_sorulari (oturum_id, soru_id, sira) VALUES (?, ?, ?)",
        (oturum_id, soru_id, sira),
    )


# ---------------------------------------------------------------------
# 5) Oturumları oynat
# ---------------------------------------------------------------------
# Her öğrencinin bir "başarı oranı" var: doğru cevap verme olasılığı.
basari = {}
for ogrenci_id in ogrenci_idleri:
    basari[ogrenci_id] = random.uniform(0.40, 0.95)


def oturum_sorulari(oturum_id):
    """Bir oturumdaki soruları sırasıyla (soru_id, dogru_cevap) listesi olarak döner."""
    return baglanti.execute(
        """SELECT os.soru_id, s.dogru_cevap
           FROM oturum_sorulari os
           JOIN sorular s ON s.id = os.soru_id
           WHERE os.oturum_id = ?
           ORDER BY os.sira""",
        (oturum_id,),
    ).fetchall()


def cevap_sec(ogrenci_id, dogru_cevap):
    """Öğrencinin başarı oranına göre doğru ya da yanlış bir şık seçer."""
    if random.random() < basari[ogrenci_id]:
        return dogru_cevap
    yanlislar = [sik for sik in "ABCD" if sik != dogru_cevap]
    return random.choice(yanlislar)


def oturumu_baslat(oturum_id, baslangic):
    baglanti.execute(
        "UPDATE oturumlar SET durum = 'suruyor', baslangic = ? WHERE id = ?",
        (zaman_metni(baslangic), oturum_id),
    )


def oturumu_bitir(oturum_id, bitis):
    baglanti.execute(
        "UPDATE oturumlar SET durum = 'bitti', bitis = ? WHERE id = ?",
        (zaman_metni(bitis), oturum_id),
    )


def katil(ogrenci_id, oturum_id, zaman):
    baglanti.execute(
        "INSERT INTO katilimlar (kullanici_id, oturum_id, katilma_zamani) VALUES (?, ?, ?)",
        (ogrenci_id, oturum_id, zaman_metni(zaman)),
    )


def cevapla(ogrenci_id, oturum_id, soru_id, cevap, zaman):
    """Cevabı kaydeder. Öğrenci aynı soruyu daha önce cevapladıysa
    yeni satır eklenmez, mevcut cevap güncellenir (UPSERT)."""
    baglanti.execute(
        """INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap, cevap_zamani)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT (kullanici_id, oturum_id, soru_id)
           DO UPDATE SET verilen_cevap = excluded.verilen_cevap,
                         cevap_zamani  = excluded.cevap_zamani""",
        (ogrenci_id, oturum_id, soru_id, cevap, zaman_metni(zaman)),
    )


# --- 5a) İlk 3 oturum: başladı, cevaplandı, bitti ---
# Bitişe eklenecek uzatma (saniye). Şimdilik hepsi tam 10 dakika (uzatma yok).
# Hoca süreyi aşsaydı buraya ör. [10, 0, 30] yazılırdı.
uzatmalar = [0, 0, 0]
baslangiclar = [datetime(2026, 9, 25, 10, 0, 0),
                datetime(2026, 9, 25, 10, 20, 0),
                datetime(2026, 9, 25, 10, 40, 0)]

for i in range(3):
    oturum_id = oturum_idleri[i]
    baslangic = baslangiclar[i]
    bitis = baslangic + timedelta(seconds=600 + uzatmalar[i])

    oturumu_baslat(oturum_id, baslangic)
    sorular_listesi = oturum_sorulari(oturum_id)

    for ogrenci_id in ogrenci_idleri:
        if random.random() > 0.90:          # öğrencilerin ~%10'u bu quize katılmaz
            continue
        katil(ogrenci_id, oturum_id, baslangic + timedelta(seconds=random.randint(0, 15)))

        for soru_id, dogru_cevap in sorular_listesi:
            if random.random() > 0.92:      # soruların ~%8'i boş bırakılır
                continue
            zaman = baslangic + timedelta(seconds=random.randint(20, 590))
            cevapla(ogrenci_id, oturum_id, soru_id, cevap_sec(ogrenci_id, dogru_cevap), zaman)

        # Bazı öğrenciler ilk sorudaki cevabını sonradan değiştirir (UPSERT örneği)
        if random.random() < 0.15:
            soru_id, dogru_cevap = sorular_listesi[0]
            zaman = baslangic + timedelta(seconds=random.randint(591, 600))
            cevapla(ogrenci_id, oturum_id, soru_id, dogru_cevap, zaman)

    oturumu_bitir(oturum_id, bitis)


# --- 5b) 4. oturum: şu an SÜRÜYOR (canlı takip için) ---
# 5 dakika önce başlamış gibi; öğrenciler soruların bir kısmına ulaşmış.
# (Normal tempo: 600 sn'de 20 soru, soru başına ~30 sn -> 5 dk'da en fazla ~10 soru)
oturum_id = oturum_idleri[3]
baslangic = datetime.now().replace(microsecond=0) - timedelta(seconds=300)
oturumu_baslat(oturum_id, baslangic)
sorular_listesi = oturum_sorulari(oturum_id)

for ogrenci_id in ogrenci_idleri:
    if random.random() > 0.85:              # öğrencilerin ~%15'i henüz katılmadı
        continue
    katil(ogrenci_id, oturum_id, baslangic + timedelta(seconds=random.randint(0, 15)))

    ulasilan_soru = random.randint(0, 10)   # katılıp hiç cevap vermemiş olan da var (0)
    for soru_id, dogru_cevap in sorular_listesi[:ulasilan_soru]:
        zaman = baslangic + timedelta(seconds=random.randint(20, 299))
        cevapla(ogrenci_id, oturum_id, soru_id, cevap_sec(ogrenci_id, dogru_cevap), zaman)

# --- 5c) 5. oturum: BAŞLAMADI (sadece soruları atanmış durumda) ---

baglanti.commit()


# ---------------------------------------------------------------------
# 6) Kayıt sayılarını doğrula
# ---------------------------------------------------------------------
print("Veritabanı oluşturuldu:", VERITABANI)
for tablo in ["kullanicilar", "oturumlar", "sorular", "oturum_sorulari", "katilimlar", "cevaplar"]:
    sayi = baglanti.execute(f"SELECT COUNT(*) FROM {tablo}").fetchone()[0]
    print(f"  {tablo:<16}: {sayi}")

ogrenci = baglanti.execute("SELECT COUNT(*) FROM kullanicilar WHERE rol = 'ogrenci'").fetchone()[0]
print(f"  (öğrenci sayısı : {ogrenci})")

for kod, durum in baglanti.execute("SELECT kod, durum FROM oturumlar ORDER BY id"):
    print(f"  {kod}: {durum}")

baglanti.close()

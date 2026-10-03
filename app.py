"""
SQLite Quiz Veri Tabanı - Küçük web arayüzü (Flask)

Ekranlar:
  /           giriş
  /ogrenci    öğrenci: süren quize katılma, cevaplama, geçmiş sonuçlar
  /hoca       hoca: kayıt sayıları, oturum başlat/bitir, canlı takip, ilk 10
  /sonuc/<id> hoca: bir oturumun sonuçları

Bütün kurallar (bitmiş quize cevap verilemez, aynı anda tek quiz vb.)
veritabanında tanımlıdır. Arayüz sadece SQL çalıştırır, veritabanı bir
işlemi reddederse hata mesajını ekranda gösterir.

Çalıştırma:  python app.py   ->   tarayıcıda http://127.0.0.1:5000

Açılışta: süren quiz 5 dakikadan uzun süredir açıksa örnek veri "bayat"
sayılır ve seed.py ile yeniden kurulur (ayrıntı: bayat_veriyi_tazele).
"""

import hashlib
import os
import sqlite3
import subprocess
import sys

from flask import Flask, flash, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "quiz-projesi-gizli-anahtar"   # oturum (giriş) bilgisini imzalamak için

VERITABANI = "quiz.db"
BAYAT_ESIGI_SN = 300   # süren quiz 5 dakikadan uzun süredir açıksa örnek veri bayat sayılır

# Veritabanının reddettiği işlemler için ekranda gösterilecek açıklamalar.
# (hata mesajında geçen ifade, kullanıcıya gösterilecek açıklama)
KURAL_ACIKLAMALARI = [
    ("oturumlar.durum",        "Aynı anda yalnızca bir quiz sürebilir. Önce süren quizi bitirin."),
    ("Oturum aktif degil",     "Quiz şu an sürmüyor: cevap kaydedilemez ya da değiştirilemez."),
    ("Oturum bitmis",          "Bitmiş bir quize katılınamaz."),
    ("Gecersiz durum gecisi",  "Quiz durumu yalnızca ileri gidebilir: başlamadı → sürüyor → bitti."),
    ("katilimlar.kullanici_id", "Bu quize zaten katıldınız."),
    ("zamani gecersiz",        "Zaman bilgisi tutarsız: quizin başlangıcından önce ya da gelecekte olamaz."),
]


def baglan():
    """Veritabanına bağlanır. Satırlara sütun adıyla erişilebilir: satir['ad']"""
    baglanti = sqlite3.connect(VERITABANI)
    baglanti.row_factory = sqlite3.Row
    baglanti.execute("PRAGMA foreign_keys = ON;")
    return baglanti


def sifre_dogru_mu(sifre, sifre_hash, sifre_salt):
    """Girilen şifreyi aynı salt ile hashler ve kayıtlı hash ile karşılaştırır."""
    ozet = hashlib.pbkdf2_hmac("sha256", sifre.encode("utf-8"), bytes.fromhex(sifre_salt), 100_000)
    return ozet.hex() == sifre_hash


def kural_aciklamasi(hata_metni):
    """Veritabanının hata mesajına uyan Türkçe açıklamayı bulur."""
    for ifade, aciklama in KURAL_ACIKLAMALARI:
        if ifade in hata_metni:
            return aciklama
    return "Bu işlem veri bütünlüğü kurallarına aykırı olduğu için reddedildi."


def islem_yap(sql, degerler):
    """Veriyi değiştiren bir SQL çalıştırır. Veritabanı reddederse, ekranda
    sarı 'kural' kutusunda göstermek üzere açıklama + asıl mesajı saklar."""
    baglanti = baglan()
    try:
        baglanti.execute(sql, degerler)
        baglanti.commit()
    except sqlite3.Error as hata:
        flash(kural_aciklamasi(str(hata)) + "||" + str(hata), "kural")
    baglanti.close()


def canli_durum(baglanti):
    """Canlı takip için kısa bir özet: süren quiz hangisi, kaç katılımcı, kaç cevap.
    'imza' bu üç bilginin birleşimidir. İmza değiştiyse ekranın yenilenmesi gerekir."""
    satir = baglanti.execute(
        """SELECT d.id,
                  (SELECT COUNT(*) FROM katilimlar k WHERE k.oturum_id = d.id) AS katilimci,
                  (SELECT COUNT(*) FROM cevaplar c   WHERE c.oturum_id = d.id) AS cevap
           FROM v_oturum_durumu d
           WHERE d.durum = 'suruyor'"""
    ).fetchone()
    if satir is None:
        return {"oturum_id": None, "imza": "yok"}
    imza = f"{satir['id']}-{satir['katilimci']}-{satir['cevap']}"
    return {"oturum_id": satir["id"], "imza": imza}


@app.route("/canli")
def canli():
    """Sayfalar bu adrese saniyede bir sorar. Cevap küçük bir JSON'dur:
    {"oturum_id": 4, "imza": "4-49-137"}"""
    baglanti = baglan()
    durum = canli_durum(baglanti)
    baglanti.close()
    return durum


# ---------------------------------------------------------------------
# GİRİŞ / ÇIKIŞ
# ---------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def giris():
    # Zaten giriş yapmış kullanıcı kendi sayfasına gider
    if request.method == "GET" and session.get("rol") == "hoca":
        return redirect(url_for("hoca"))
    if request.method == "GET" and session.get("rol") == "ogrenci":
        return redirect(url_for("ogrenci"))

    if request.method == "POST":
        baglanti = baglan()
        kullanici = baglanti.execute(
            "SELECT * FROM kullanicilar WHERE email = ?", (request.form["email"],)
        ).fetchone()
        baglanti.close()

        if kullanici and sifre_dogru_mu(request.form["sifre"], kullanici["sifre_hash"], kullanici["sifre_salt"]):
            session["kullanici_id"] = kullanici["id"]
            session["ad"] = kullanici["ad"] + " " + kullanici["soyad"]
            session["rol"] = kullanici["rol"]
            if kullanici["rol"] == "hoca":
                return redirect(url_for("hoca"))
            return redirect(url_for("ogrenci"))

        flash("E-posta veya şifre hatalı.")
    return render_template("giris.html")


@app.route("/cikis")
def cikis():
    session.clear()
    return redirect(url_for("giris"))


# ---------------------------------------------------------------------
# ÖĞRENCİ
# ---------------------------------------------------------------------
@app.route("/ogrenci")
def ogrenci():
    if session.get("rol") != "ogrenci":
        return redirect(url_for("giris"))
    kullanici_id = session["kullanici_id"]
    baglanti = baglan()

    # Şu an süren quiz (en fazla bir tane olabilir)
    oturum = baglanti.execute(
        "SELECT * FROM v_oturum_durumu WHERE durum = 'suruyor'"
    ).fetchone()

    katildi = False
    sorular = []
    cevaplar = {}       # soru_id -> öğrencinin verdiği cevap
    if oturum:
        katildi = baglanti.execute(
            "SELECT COUNT(*) FROM katilimlar WHERE kullanici_id = ? AND oturum_id = ?",
            (kullanici_id, oturum["id"]),
        ).fetchone()[0] == 1

        if katildi:
            sorular = baglanti.execute(
                """SELECT os.sira, s.*
                   FROM oturum_sorulari os
                   JOIN sorular s ON s.id = os.soru_id
                   WHERE os.oturum_id = ?
                   ORDER BY os.sira""",
                (oturum["id"],),
            ).fetchall()
            for satir in baglanti.execute(
                "SELECT soru_id, verilen_cevap FROM cevaplar WHERE kullanici_id = ? AND oturum_id = ?",
                (kullanici_id, oturum["id"]),
            ):
                cevaplar[satir["soru_id"]] = satir["verilen_cevap"]

    # Öğrencinin bitmiş quizlerdeki sonuçları ("18/20 · %90")
    sonuclar = baglanti.execute(
        """SELECT o.kod, o.baslik, o.bitis, r.dogru, r.soru_sayisi, r.yuzde
           FROM v_sonuclar r
           JOIN oturumlar o ON o.id = r.oturum_id
           WHERE r.kullanici_id = ? AND o.durum = 'bitti'
           ORDER BY o.id""",
        (kullanici_id,),
    ).fetchall()
    baglanti.close()

    return render_template("ogrenci.html", oturum=oturum, katildi=katildi,
                           sorular=sorular, cevaplar=cevaplar, sonuclar=sonuclar)


@app.route("/katil", methods=["POST"])
def katil():
    if session.get("rol") != "ogrenci":
        return redirect(url_for("giris"))
    islem_yap(
        "INSERT INTO katilimlar (kullanici_id, oturum_id) VALUES (?, ?)",
        (session["kullanici_id"], request.form["oturum_id"]),
    )
    return redirect(url_for("ogrenci"))


@app.route("/cevap", methods=["POST"])
def cevap():
    if session.get("rol") != "ogrenci":
        return redirect(url_for("giris"))
    # UPSERT: ilk cevapta satır eklenir, sonraki cevaplarda aynı satır güncellenir
    islem_yap(
        """INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap)
           VALUES (?, ?, ?, ?)
           ON CONFLICT (kullanici_id, oturum_id, soru_id)
           DO UPDATE SET verilen_cevap = excluded.verilen_cevap,
                         cevap_zamani  = datetime('now', 'localtime')""",
        (session["kullanici_id"], request.form["oturum_id"],
         request.form["soru_id"], request.form["cevap"]),
    )
    return redirect(url_for("ogrenci") + "#soru" + request.form["sira"])


# ---------------------------------------------------------------------
# HOCA
# ---------------------------------------------------------------------
@app.route("/hoca")
def hoca():
    if session.get("rol") != "hoca":
        return redirect(url_for("giris"))
    baglanti = baglan()

    # Kayıt sayıları (queries.sql A1)
    sayilar = baglanti.execute(
        """SELECT
             (SELECT COUNT(*) FROM kullanicilar WHERE rol = 'ogrenci') AS ogrenci,
             (SELECT COUNT(*) FROM oturumlar)                         AS oturum,
             (SELECT COUNT(DISTINCT soru_id) FROM oturum_sorulari)    AS soru,
             (SELECT COUNT(*) FROM cevaplar)                          AS cevap"""
    ).fetchone()

    # Tüm oturumların durumu, süresi ve uzatması (queries.sql B1)
    oturumlar = baglanti.execute("SELECT * FROM v_oturum_durumu ORDER BY id").fetchall()

    # Süren oturumun anlık ilerlemesi (queries.sql B2)
    ilerleme = baglanti.execute(
        """SELECT
             d.kod, d.baslik, d.gecen_sure_sn, d.uzatma_sn,
             (SELECT COUNT(*) FROM katilimlar k       WHERE k.oturum_id  = d.id) AS katilimci,
             (SELECT COUNT(*) FROM oturum_sorulari os WHERE os.oturum_id = d.id) AS soru_sayisi,
             (SELECT COUNT(*) FROM cevaplar c         WHERE c.oturum_id  = d.id) AS verilen_cevap
           FROM v_oturum_durumu d
           WHERE d.durum = 'suruyor'"""
    ).fetchone()

    # Süren oturumda öğrenci bazında ilerleme (queries.sql B4)
    ogrenciler = baglanti.execute(
        """SELECT u.ogrenci_no, u.ad || ' ' || u.soyad AS ogrenci,
                  r.cevaplanan, r.soru_sayisi
           FROM v_sonuclar r
           JOIN oturumlar o    ON o.id = r.oturum_id
           JOIN kullanicilar u ON u.id = r.kullanici_id
           WHERE o.durum = 'suruyor'
           ORDER BY r.cevaplanan DESC, u.ogrenci_no"""
    ).fetchall()

    # En yüksek puanlı 10 kullanıcı (queries.sql C3)
    ilk10 = baglanti.execute(
        """SELECT u.ogrenci_no, u.ad || ' ' || u.soyad AS ogrenci,
                  COUNT(*) AS katildigi_quiz, SUM(r.dogru) AS toplam_dogru,
                  ROUND(100.0 * SUM(r.dogru) /
                        (SELECT COUNT(*) FROM oturum_sorulari os
                           JOIN oturumlar o2 ON o2.id = os.oturum_id
                          WHERE o2.durum = 'bitti'), 1) AS genel_yuzde
           FROM v_sonuclar r
           JOIN oturumlar o    ON o.id = r.oturum_id
           JOIN kullanicilar u ON u.id = r.kullanici_id
           WHERE o.durum = 'bitti'
           GROUP BY u.id
           ORDER BY genel_yuzde DESC, u.ogrenci_no
           LIMIT 10"""
    ).fetchall()
    durum = canli_durum(baglanti)
    baglanti.close()

    return render_template("hoca.html", sayilar=sayilar, oturumlar=oturumlar,
                           ilerleme=ilerleme, ogrenciler=ogrenciler, ilk10=ilk10,
                           imza=durum["imza"])


@app.route("/oturum/<int:oturum_id>/baslat", methods=["POST"])
def oturum_baslat(oturum_id):
    if session.get("rol") != "hoca":
        return redirect(url_for("giris"))
    islem_yap(
        "UPDATE oturumlar SET durum = 'suruyor', baslangic = datetime('now', 'localtime') WHERE id = ?",
        (oturum_id,),
    )
    return redirect(url_for("hoca"))


@app.route("/oturum/<int:oturum_id>/bitir", methods=["POST"])
def oturum_bitir(oturum_id):
    if session.get("rol") != "hoca":
        return redirect(url_for("giris"))
    islem_yap(
        "UPDATE oturumlar SET durum = 'bitti', bitis = datetime('now', 'localtime') WHERE id = ?",
        (oturum_id,),
    )
    return redirect(url_for("hoca"))


@app.route("/sonuc/<int:oturum_id>")
def sonuc(oturum_id):
    if session.get("rol") != "hoca":
        return redirect(url_for("giris"))
    baglanti = baglan()

    oturum = baglanti.execute("SELECT * FROM v_oturum_durumu WHERE id = ?", (oturum_id,)).fetchone()

    # Oturum özeti (queries.sql C2)
    ozet = baglanti.execute(
        """SELECT COUNT(*) AS katilimci, ROUND(AVG(yuzde), 1) AS ortalama,
                  MAX(yuzde) AS en_yuksek, MIN(yuzde) AS en_dusuk
           FROM v_sonuclar WHERE oturum_id = ?""",
        (oturum_id,),
    ).fetchone()

    # Öğrenci sonuçları (queries.sql C1)
    sonuclar = baglanti.execute(
        """SELECT u.ogrenci_no, u.ad || ' ' || u.soyad AS ogrenci,
                  r.dogru, r.yanlis, r.bos, r.soru_sayisi, r.yuzde
           FROM v_sonuclar r
           JOIN kullanicilar u ON u.id = r.kullanici_id
           WHERE r.oturum_id = ?
           ORDER BY r.yuzde DESC, u.ogrenci_no""",
        (oturum_id,),
    ).fetchall()
    baglanti.close()

    return render_template("sonuc.html", oturum=oturum, ozet=ozet, sonuclar=sonuclar)


# ---------------------------------------------------------------------
# AÇILIŞTA BAYAT VERİ KONTROLÜ
# ---------------------------------------------------------------------
def bayat_veriyi_tazele():
    """Örnek veride bir quiz 'sürüyor' olarak bırakılır. seed.py'den günler sonra
    açılırsa bu quiz günlerdir sürüyor görünür. Bu yüzden açılışta bir kez bakılır:
    quiz.db yoksa ya da süren quiz 5 dakikadan uzun süredir açıksa seed.py çalıştırılır.
    Uygulama çalışırken bir daha kontrol edilmez, yapılan işlemler korunur."""
    if not os.path.exists(VERITABANI):
        print("quiz.db bulunamadı, örnek veri kuruluyor (python seed.py)...")
        subprocess.run([sys.executable, "seed.py"], check=True)
        return

    baglanti = baglan()
    oturum = baglanti.execute(
        "SELECT kod, gecen_sure_sn FROM v_oturum_durumu WHERE durum = 'suruyor'"
    ).fetchone()
    baglanti.close()

    if oturum and oturum["gecen_sure_sn"] > BAYAT_ESIGI_SN:
        dakika = oturum["gecen_sure_sn"] // 60
        print(f"Süren quiz ({oturum['kod']}) {dakika // 60} saat {dakika % 60} dakikadır "
              "açık görünüyordu: örnek veri bayat.")
        print("Örnek veri yeniden kuruluyor (python seed.py)...")
        subprocess.run([sys.executable, "seed.py"], check=True)


if __name__ == "__main__":
    bayat_veriyi_tazele()
    app.run(debug=True)

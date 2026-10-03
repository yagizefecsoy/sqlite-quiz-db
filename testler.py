"""
SQLite Quiz Veri Tabanı - Veri bütünlüğü testleri

Her test, kurallara AYKIRI bir işlem dener ve veritabanının bu işlemi
reddettiğini doğrular. Birkaç test de kurallara UYGUN işlemlerin
kabul edildiğini doğrular (kurallar doğru işlemleri engellememeli).

Sonunda bütün değişiklikler geri alınır (rollback): quiz.db DEĞİŞMEZ.

Çalıştırma:  python seed.py   (temiz veri için, bir kez)
             python testler.py

Kullanılan kayıtlar (seed.py ile oluşan veriden):
  oturum 1 = w01-s01 (bitti), oturum 5 = w02-s02 (baslamadi, test sırasında başlatılır)
  kullanıcı 1  = hoca (hiçbir oturuma katılmadı)
  kullanıcı 2  = öğrenci 20240001 (oturum 1'e katıldı, 1. soruyu cevapladı)
  kullanıcı 4  = öğrenci 20240003 (oturum 1'e katılmadı)
  kullanıcı 20 = öğrenci 20240019 (test sırasında oturum 5'e katılır)
  soru 1 = oturum 1'in sorusu, soru 81 = oturum 5'in 1. sorusu (doğru cevap A)
"""

import sqlite3

baglanti = sqlite3.connect("quiz.db")
baglanti.execute("PRAGMA foreign_keys = ON;")

sonuclar = []   # her test için True (geçti) ya da False (kaldı)


def reddedilmeli(aciklama, sql):
    """Bu işlem kurallara aykırı: veritabanı HATA vermeli."""
    try:
        baglanti.execute(sql)
    except sqlite3.Error as hata:
        print(f"  [OK]   {aciklama}")
        print(f"         -> reddedildi: {hata}")
        sonuclar.append(True)
    else:
        print(f"  [HATA] {aciklama}")
        print(f"         -> KABUL EDİLDİ, reddedilmesi gerekiyordu!")
        sonuclar.append(False)


def kabul_edilmeli(aciklama, sql):
    """Bu işlem kurallara uygun: veritabanı KABUL etmeli."""
    try:
        baglanti.execute(sql)
    except sqlite3.Error as hata:
        print(f"  [HATA] {aciklama}")
        print(f"         -> reddedildi: {hata}, kabul edilmesi gerekiyordu!")
        sonuclar.append(False)
    else:
        print(f"  [OK]   {aciklama}")
        print(f"         -> kabul edildi")
        sonuclar.append(True)


def sayi(sql):
    """Tek bir değer döndüren sorguyu çalıştırır."""
    return baglanti.execute(sql).fetchone()[0]


# ---------------------------------------------------------------------
print("\n0) HAZIRLIK: quiz başlar, öğrenci katılır")
# ---------------------------------------------------------------------
reddedilmeli(
    "BAŞLAMAMIŞ oturuma cevap",
    "INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap) VALUES (20, 5, 81, 'A')")

kabul_edilmeli(
    "Hoca başlamamış oturumu (w02-s02) başlatır",
    "UPDATE oturumlar SET durum = 'suruyor', baslangic = datetime('now', 'localtime') WHERE id = 5")

kabul_edilmeli(
    "Öğrenci süren oturuma katılır",
    "INSERT INTO katilimlar (kullanici_id, oturum_id) VALUES (20, 5)")


# ---------------------------------------------------------------------
print("\n1) CEVAPLAR")
# ---------------------------------------------------------------------
kabul_edilmeli(
    "Süren oturuma, katılmış öğrencinin, oturumdaki soruya geçerli cevabı",
    "INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap) VALUES (20, 5, 81, 'B')")

reddedilmeli(
    "Aynı soruya ikinci cevap SATIRI (tekrar kayıt)",
    "INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap) VALUES (20, 5, 81, 'C')")

kabul_edilmeli(
    "Aynı soruya cevap DEĞİŞTİRME (UPSERT: satır eklenmez, güncellenir)",
    """INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap) VALUES (20, 5, 81, 'A')
       ON CONFLICT (kullanici_id, oturum_id, soru_id) DO UPDATE SET verilen_cevap = excluded.verilen_cevap""")

satir = sayi("SELECT COUNT(*) FROM cevaplar WHERE kullanici_id = 20 AND oturum_id = 5 AND soru_id = 81")
deger = sayi("SELECT verilen_cevap FROM cevaplar WHERE kullanici_id = 20 AND oturum_id = 5 AND soru_id = 81")
print(f"         -> kontrol: bu soru için {satir} satır var, değeri '{deger}'")
sonuclar.append(satir == 1 and deger == "A")

reddedilmeli(
    "Olmayan kullanıcı (id 999) adına cevap",
    "INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap) VALUES (999, 5, 81, 'A')")

reddedilmeli(
    "Olmayan soruya (id 9999) cevap",
    "INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap) VALUES (20, 5, 9999, 'A')")

reddedilmeli(
    "Oturumda BULUNMAYAN soruya cevap (soru 1, oturum 1'in sorusu)",
    "INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap) VALUES (20, 5, 1, 'A')")

reddedilmeli(
    "Oturuma katılmamış kullanıcının cevabı (hoca, id 1)",
    "INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap) VALUES (1, 5, 81, 'A')")

reddedilmeli(
    "Geçersiz şık ('E')",
    "INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap) VALUES (20, 5, 82, 'E')")

reddedilmeli(
    "BİTMİŞ oturuma yeni cevap",
    "INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap) VALUES (2, 1, 2, 'A')")

reddedilmeli(
    "BİTMİŞ oturumda cevap değiştirme",
    "UPDATE cevaplar SET verilen_cevap = 'D' WHERE kullanici_id = 2 AND oturum_id = 1 AND soru_id = 1")


# ---------------------------------------------------------------------
print("\n2) KATILIMLAR")
# ---------------------------------------------------------------------
reddedilmeli(
    "Aynı öğrencinin aynı oturuma ikinci kez katılması",
    "INSERT INTO katilimlar (kullanici_id, oturum_id) VALUES (20, 5)")

reddedilmeli(
    "BİTMİŞ oturuma katılım",
    "INSERT INTO katilimlar (kullanici_id, oturum_id) VALUES (4, 1)")

reddedilmeli(
    "Olmayan oturuma (id 99) katılım",
    "INSERT INTO katilimlar (kullanici_id, oturum_id) VALUES (4, 99)")


# ---------------------------------------------------------------------
print("\n3) OTURUM - SORU İLİŞKİSİ")
# ---------------------------------------------------------------------
reddedilmeli(
    "Aynı soruyu aynı oturuma ikinci kez ekleme",
    "INSERT INTO oturum_sorulari (oturum_id, soru_id, sira) VALUES (5, 81, 21)")

reddedilmeli(
    "Bir oturumda aynı sıra numarasını ikinci kez kullanma",
    "INSERT INTO oturum_sorulari (oturum_id, soru_id, sira) VALUES (5, 1, 1)")

reddedilmeli(
    "Cevapları olan bir soruyu silme",
    "DELETE FROM sorular WHERE id = 1")


# ---------------------------------------------------------------------
print("\n4) OTURUM DURUMU VE ZAMANLAR")
# ---------------------------------------------------------------------
reddedilmeli(
    "Bir oturum sürerken ikinci bir süren oturum",
    """INSERT INTO oturumlar (kod, baslik, hafta, durum, baslangic)
       VALUES ('w09-s03', 'Deneme', 9, 'suruyor', datetime('now', 'localtime'))""")

reddedilmeli(
    "Durumu geri alma (bitti -> suruyor)",
    "UPDATE oturumlar SET durum = 'suruyor', bitis = NULL WHERE id = 1")

reddedilmeli(
    "Bitiş zamanı olmadan 'bitti' durumuna geçme",
    "UPDATE oturumlar SET durum = 'bitti' WHERE id = 5")

reddedilmeli(
    "Bitiş zamanı başlangıçtan önce olan oturum",
    """INSERT INTO oturumlar (kod, baslik, hafta, durum, baslangic, bitis)
       VALUES ('w09-s01', 'Deneme', 9, 'bitti', '2026-10-01 10:00:00', '2026-10-01 09:00:00')""")

reddedilmeli(
    "Geçersiz durum değeri ('iptal')",
    "INSERT INTO oturumlar (kod, baslik, hafta, durum) VALUES ('w09-s02', 'Deneme', 9, 'iptal')")

reddedilmeli(
    "Aynı oturum kodunu (w01-s01) ikinci kez kullanma",
    "INSERT INTO oturumlar (kod, baslik, hafta) VALUES ('w01-s01', 'Kopya', 1)")


# ---------------------------------------------------------------------
print("\n5) KULLANICILAR VE SORULAR")
# ---------------------------------------------------------------------
reddedilmeli(
    "Kayıtlı e-postayı BÜYÜK harfle tekrar kullanma",
    """INSERT INTO kullanicilar (ogrenci_no, ad, soyad, email, sifre_hash, sifre_salt)
       VALUES ('20249999', 'Test', 'Kişi', '20240001@OGRENCI.EDU.TR', 'x', 'y')""")

reddedilmeli(
    "Kayıtlı öğrenci numarasını tekrar kullanma",
    """INSERT INTO kullanicilar (ogrenci_no, ad, soyad, email, sifre_hash, sifre_salt)
       VALUES ('20240001', 'Test', 'Kişi', 'yeni@ogrenci.edu.tr', 'x', 'y')""")

reddedilmeli(
    "Öğrenci numarası olmayan öğrenci",
    """INSERT INTO kullanicilar (ogrenci_no, ad, soyad, email, sifre_hash, sifre_salt)
       VALUES (NULL, 'Test', 'Kişi', 'numarasiz@ogrenci.edu.tr', 'x', 'y')""")

reddedilmeli(
    "Geçersiz e-posta biçimi",
    """INSERT INTO kullanicilar (ogrenci_no, ad, soyad, email, sifre_hash, sifre_salt)
       VALUES ('20249998', 'Test', 'Kişi', 'gecersiz-eposta', 'x', 'y')""")

reddedilmeli(
    "Doğru cevabı 'X' olan soru",
    """INSERT INTO sorular (metin, secenek_a, secenek_b, secenek_c, secenek_d, dogru_cevap, konu)
       VALUES ('Deneme sorusu?', '1', '2', '3', '4', 'X', 'Deneme')""")


# ---------------------------------------------------------------------
# Özet ve geri alma
# ---------------------------------------------------------------------
baglanti.rollback()      # yapılan her şeyi geri al: quiz.db değişmez
baglanti.close()

gecen = sonuclar.count(True)
print(f"\nSONUÇ: {len(sonuclar)} kontrolden {gecen} tanesi beklendiği gibi.")
if gecen == len(sonuclar):
    print("Bütün kurallar çalışıyor.")
else:
    print("DİKKAT: Beklenmeyen sonuçlar var, yukarıdaki [HATA] satırlarına bakın.")

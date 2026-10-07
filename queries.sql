-- =====================================================================
-- SQLite Quiz Veri Tabanı - Sorgular
--
--   A. Kayıt sayılarının doğrulanması
--   B. Canlı takip (süren oturum)
--   C. Sonuçlar ve puan sıralaması
--   D. Akış denemesi: oturum başlat -> katıl -> cevapla -> bitir
--
-- A, B ve C bölümleri yalnızca OKUR (SELECT), istenildiği kadar çalıştırılabilir.
-- D bölümü veriyi DEĞİŞTİRİR. Başa dönmek için:  python seed.py
--
-- Puan hesabı schema.sql içindeki v_sonuclar görünümündedir,
-- süre hesabı v_oturum_durumu görünümündedir.
-- =====================================================================

PRAGMA foreign_keys = ON;


-- =====================================================================
-- A. KAYIT SAYILARI
-- =====================================================================

-- A1. Her tablodaki kayıt sayısı (hedef: 50+ öğrenci, 5 oturum, 100+ soru)
SELECT 'ogrenciler'      AS tablo, COUNT(*) AS kayit FROM kullanicilar WHERE rol = 'ogrenci'
UNION ALL
SELECT 'kullanicilar',    COUNT(*) FROM kullanicilar
UNION ALL
SELECT 'oturumlar',       COUNT(*) FROM oturumlar
UNION ALL
SELECT 'sorular',         COUNT(*) FROM sorular
UNION ALL
SELECT 'oturum_sorulari', COUNT(*) FROM oturum_sorulari
UNION ALL
SELECT 'katilimlar',      COUNT(*) FROM katilimlar
UNION ALL
SELECT 'cevaplar',        COUNT(*) FROM cevaplar;

-- A2. Oturumlara atanmış FARKLI soru sayısı
-- (Aynı soru birden çok oturumda olsa bile bir kez sayılır, hedef: 100)
SELECT COUNT(DISTINCT soru_id) AS farkli_soru_sayisi
FROM oturum_sorulari;

-- A3. Her oturumdaki soru sayısı
SELECT o.kod, o.baslik, COUNT(os.soru_id) AS soru_sayisi
FROM oturumlar o
LEFT JOIN oturum_sorulari os ON os.oturum_id = o.id
GROUP BY o.id
ORDER BY o.id;


-- =====================================================================
-- B. CANLI TAKİP
-- "Canlı" = sorgu her çalıştırıldığında güncel veriyi yeniden okur.
-- Süren oturum, durum = 'suruyor' koşuluyla kendiliğinden bulunur.
-- NOT (örnek veri): süren quiz (w02-s01), seed.py çalıştığı andan 5 dk önce başlamış
-- kaydedilir ve süre o andan beri işler. Geçen süre çok büyük görünüyorsa veri eskidir.
-- Taze görmek için: python seed.py (python app.py açılışta kendisi tazeler).
-- =====================================================================

-- B1. Tüm oturumların durumu, geçen süre ve planlanan süreyi (10 dk) aşan uzatma
SELECT kod, baslik, durum, baslangic, bitis,
       gecen_sure_sn,
       uzatma_sn
FROM v_oturum_durumu
ORDER BY id;

-- B2. Süren oturumun anlık ilerlemesi
--     katılımcı sayısı, verilen cevap sayısı ve tamamlanma yüzdesi
SELECT
    kod,
    gecen_sure_sn,
    katilimci,
    ogrenci_sayisi - katilimci             AS katilmayan,
    verilen_cevap,
    katilimci * soru_sayisi                AS beklenen_cevap,
    ROUND(100.0 * verilen_cevap / (katilimci * soru_sayisi), 1) AS tamamlanma_yuzdesi
FROM (
    SELECT
        d.kod,
        d.gecen_sure_sn,
        (SELECT COUNT(*) FROM katilimlar k      WHERE k.oturum_id  = d.id) AS katilimci,
        (SELECT COUNT(*) FROM oturum_sorulari os WHERE os.oturum_id = d.id) AS soru_sayisi,
        (SELECT COUNT(*) FROM cevaplar c        WHERE c.oturum_id  = d.id) AS verilen_cevap,
        (SELECT COUNT(*) FROM kullanicilar WHERE rol = 'ogrenci')           AS ogrenci_sayisi
    FROM v_oturum_durumu d
    WHERE d.durum = 'suruyor'
);

-- B3. Süren oturumda soru bazında ilerleme: her soruyu kaç kişi cevapladı
SELECT
    os.sira,
    s.konu,
    COUNT(c.id) AS cevaplayan
FROM oturumlar o
JOIN oturum_sorulari os ON os.oturum_id = o.id
JOIN sorular s          ON s.id = os.soru_id
LEFT JOIN cevaplar c    ON c.oturum_id = os.oturum_id
                       AND c.soru_id   = os.soru_id
WHERE o.durum = 'suruyor'
GROUP BY os.sira, s.konu
ORDER BY os.sira;

-- B4. Süren oturumda öğrenci bazında ilerleme
--     (katılıp henüz hiç cevap vermeyenler de listelenir: cevaplanan = 0)
SELECT
    u.ogrenci_no,
    u.ad || ' ' || u.soyad AS ogrenci,
    r.cevaplanan || '/' || r.soru_sayisi AS ilerleme
FROM v_sonuclar r
JOIN oturumlar o    ON o.id = r.oturum_id
JOIN kullanicilar u ON u.id = r.kullanici_id
WHERE o.durum = 'suruyor'
ORDER BY r.cevaplanan DESC, u.ogrenci_no;


-- =====================================================================
-- C. SONUÇLAR VE PUAN SIRALAMASI
-- Puanlama: doğru = 1, yanlış = 0, boş = 0 ve yüzde = doğru / soru sayısı * 100
-- =====================================================================

-- C1. Bir oturumun sonuçları (başka oturum için kodu değiştirin)
--     Görünüm, quiz sistemindeki "18/20 · %90" biçimindedir.
SELECT
    u.ogrenci_no,
    u.ad || ' ' || u.soyad AS ogrenci,
    r.dogru,
    r.yanlis,
    r.bos,
    r.dogru || '/' || r.soru_sayisi || ' · %' || r.yuzde AS sonuc
FROM v_sonuclar r
JOIN oturumlar o    ON o.id = r.oturum_id
JOIN kullanicilar u ON u.id = r.kullanici_id
WHERE o.kod = 'w01-s01'
ORDER BY r.yuzde DESC, u.ogrenci_no;

-- C2. Oturum özetleri: katılımcı sayısı, sınıf ortalaması, en yüksek ve en düşük
SELECT
    o.kod,
    o.durum,
    COUNT(*)            AS katilimci,
    ROUND(AVG(r.yuzde), 1) AS ortalama_yuzde,
    MAX(r.yuzde)        AS en_yuksek,
    MIN(r.yuzde)        AS en_dusuk
FROM v_sonuclar r
JOIN oturumlar o ON o.id = r.oturum_id
GROUP BY o.id
ORDER BY o.id;

-- C3. En yüksek puanlı 10 kullanıcı (bitmiş oturumların tamamı üzerinden)
--     Genel yüzde = bitmiş oturumlardaki toplam doğru / bitmiş oturumlardaki toplam soru
--     Katılınmayan quizin soruları da paydadadır, yani o quiz 0 sayılır.
SELECT
    u.ogrenci_no,
    u.ad || ' ' || u.soyad AS ogrenci,
    COUNT(*)               AS katildigi_quiz,
    SUM(r.dogru)           AS toplam_dogru,
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
LIMIT 10;

-- C4. En zor 5 soru (bitmiş oturumlarda doğru cevaplanma oranı en düşük olanlar)
SELECT
    o.kod,
    os.sira,
    s.metin,
    COUNT(c.id) AS cevaplayan,
    SUM(CASE WHEN c.verilen_cevap = s.dogru_cevap THEN 1 ELSE 0 END) AS dogru,
    ROUND(100.0 * SUM(CASE WHEN c.verilen_cevap = s.dogru_cevap THEN 1 ELSE 0 END)
          / COUNT(c.id), 1) AS dogru_orani
FROM oturumlar o
JOIN oturum_sorulari os ON os.oturum_id = o.id
JOIN sorular s          ON s.id = os.soru_id
JOIN cevaplar c         ON c.oturum_id = os.oturum_id
                       AND c.soru_id   = os.soru_id
WHERE o.durum = 'bitti'
GROUP BY os.oturum_id, os.soru_id
ORDER BY dogru_orani
LIMIT 5;


-- =====================================================================
-- D. AKIŞ DENEMESİ (veriyi DEĞİŞTİRİR, başa dönmek için: python seed.py)
-- Başlamamış oturum w02-s02 (id = 5) üzerinde tam bir quiz akışı:
-- öğrenci: id = 2 (20240001), soru: id = 81 (w02-s02'nin 1. sorusu, doğru cevap A)
-- Aynı anda tek oturum sürebildiği için önce süren w02-s01 bitirilir.
-- =====================================================================

-- D0. Hoca süren oturumu (w02-s01) bitirir
UPDATE oturumlar
SET durum = 'bitti', bitis = datetime('now', 'localtime')
WHERE kod = 'w02-s01';

-- D1. Hoca yeni oturumu başlatır
UPDATE oturumlar
SET durum = 'suruyor', baslangic = datetime('now', 'localtime')
WHERE kod = 'w02-s02';

-- D2. Öğrenci oturuma katılır
INSERT INTO katilimlar (kullanici_id, oturum_id)
VALUES (2, 5);

-- D3. Öğrenci 1. soruya B cevabını verir (cevap kaydetme)
INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap)
VALUES (2, 5, 81, 'B')
ON CONFLICT (kullanici_id, oturum_id, soru_id)
DO UPDATE SET verilen_cevap = excluded.verilen_cevap,
              cevap_zamani  = datetime('now', 'localtime');

-- D4. Öğrenci fikrini değiştirip A der: aynı komut, yeni satır EKLEMEZ, günceller
INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap)
VALUES (2, 5, 81, 'A')
ON CONFLICT (kullanici_id, oturum_id, soru_id)
DO UPDATE SET verilen_cevap = excluded.verilen_cevap,
              cevap_zamani  = datetime('now', 'localtime');

-- D5. Kontrol: bu öğrencinin bu oturumda tek bir cevap satırı var, değeri 'A'
SELECT kullanici_id, oturum_id, soru_id, verilen_cevap, cevap_zamani
FROM cevaplar
WHERE kullanici_id = 2 AND oturum_id = 5;

-- D6. Hoca oturumu bitirir
UPDATE oturumlar
SET durum = 'bitti', bitis = datetime('now', 'localtime')
WHERE kod = 'w02-s02';

-- D7. Sonuç: 20 sorudan 1 doğru, 19 boş -> 1/20 · %5
SELECT kullanici_id, dogru, yanlis, bos, yuzde
FROM v_sonuclar
WHERE oturum_id = 5;

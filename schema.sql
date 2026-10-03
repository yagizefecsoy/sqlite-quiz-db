-- =====================================================================
-- SQLite Quiz Veri Tabanı - Şema
-- Tablolar, kısıtlar, indeksler, tetikleyiciler (trigger) ve görünümler (view)
-- Çalıştırma:  sqlite3 quiz.db ".read schema.sql"
-- =====================================================================

-- SQLite'ta yabancı anahtar denetimi varsayılan olarak KAPALIDIR.
-- Bu ayar bağlantıya özeldir: her yeni bağlantıda tekrar açılmalıdır.
PRAGMA foreign_keys = ON;

-- Şema tekrar çalıştırılabilsin diye eski tablolar silinir.
-- Sıra önemli: önce görünümler, sonra başka tabloya bağlı olan (çocuk) tablolar silinir.
DROP VIEW IF EXISTS v_sonuclar;
DROP VIEW IF EXISTS v_oturum_durumu;
DROP TABLE IF EXISTS cevaplar;
DROP TABLE IF EXISTS katilimlar;
DROP TABLE IF EXISTS oturum_sorulari;
DROP TABLE IF EXISTS sorular;
DROP TABLE IF EXISTS oturumlar;
DROP TABLE IF EXISTS kullanicilar;


-- ---------------------------------------------------------------------
-- 1) KULLANICILAR: öğrenciler ve hoca
-- ---------------------------------------------------------------------
CREATE TABLE kullanicilar (
    id            INTEGER PRIMARY KEY,
    ogrenci_no    TEXT UNIQUE,                       -- hocanın öğrenci numarası yok (NULL)
    ad            TEXT NOT NULL,
    soyad         TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE, -- büyük/küçük harf farkı gözetmez
    sifre_hash    TEXT NOT NULL,                     -- şifrenin kendisi değil, özeti
    sifre_salt    TEXT NOT NULL,                     -- kullanıcıya özel rastgele değer
    rol           TEXT NOT NULL DEFAULT 'ogrenci',
    kayit_zamani  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),

    CHECK (rol IN ('ogrenci', 'hoca')),
    CHECK (email LIKE '%_@_%._%'),                   -- basit e-posta biçim kontrolü
    CHECK (rol = 'hoca' OR ogrenci_no IS NOT NULL)   -- öğrencinin numarası zorunlu
);


-- ---------------------------------------------------------------------
-- 2) OTURUMLAR: her biri tek bir quiz (ör. w02-s01)
-- ---------------------------------------------------------------------
CREATE TABLE oturumlar (
    id                 INTEGER PRIMARY KEY,
    kod                TEXT NOT NULL UNIQUE,         -- ör. 'w02-s01'
    baslik             TEXT NOT NULL,                -- ör. 'Week 2 · Session 1'
    hafta              INTEGER NOT NULL,
    durum              TEXT NOT NULL DEFAULT 'baslamadi',
    planlanan_sure_sn  INTEGER NOT NULL DEFAULT 180, -- resmi süre: 3 dakika
    baslangic          TEXT,                         -- hoca başlatınca dolar
    bitis              TEXT,                         -- hoca bitirince dolar

    CHECK (hafta > 0),
    CHECK (planlanan_sure_sn > 0),
    CHECK (durum IN ('baslamadi', 'suruyor', 'bitti')),

    -- Durum ile zamanlar tutarlı olmalı (isim verildi: hata mesajında görünür)
    CONSTRAINT durum_zaman_tutarliligi CHECK (
        (durum = 'baslamadi' AND baslangic IS NULL     AND bitis IS NULL)
     OR (durum = 'suruyor'   AND baslangic IS NOT NULL AND bitis IS NULL)
     OR (durum = 'bitti'     AND baslangic IS NOT NULL AND bitis IS NOT NULL
                             AND bitis >= baslangic)
    )
);


-- ---------------------------------------------------------------------
-- 3) SORULAR: soru bankası (4 şıklı, tek doğru cevap)
-- ---------------------------------------------------------------------
CREATE TABLE sorular (
    id           INTEGER PRIMARY KEY,
    metin        TEXT NOT NULL UNIQUE,               -- aynı soru iki kez eklenemez
    secenek_a    TEXT NOT NULL,
    secenek_b    TEXT NOT NULL,
    secenek_c    TEXT NOT NULL,
    secenek_d    TEXT NOT NULL,
    dogru_cevap  TEXT NOT NULL,
    konu         TEXT NOT NULL,                      -- ör. 'JOIN', 'GROUP BY'

    CHECK (dogru_cevap IN ('A', 'B', 'C', 'D'))
);


-- ---------------------------------------------------------------------
-- 4) OTURUM_SORULARI: hangi soru hangi oturumda, kaçıncı sırada
--    (oturumlar ile sorular arasındaki çoka-çok ilişkinin ara tablosu)
-- ---------------------------------------------------------------------
CREATE TABLE oturum_sorulari (
    oturum_id  INTEGER NOT NULL REFERENCES oturumlar(id),
    soru_id    INTEGER NOT NULL REFERENCES sorular(id),
    sira       INTEGER NOT NULL,

    PRIMARY KEY (oturum_id, soru_id),  -- aynı soru aynı oturuma iki kez eklenemez
    UNIQUE (oturum_id, sira),          -- bir oturumda aynı sıra numarası iki kez olamaz
    CHECK (sira > 0)
);


-- ---------------------------------------------------------------------
-- 5) KATILIMLAR: öğrencinin oturuma katıldığı an
--    (henüz hiç cevap vermemiş olsa bile kaydı tutulur)
-- ---------------------------------------------------------------------
CREATE TABLE katilimlar (
    kullanici_id    INTEGER NOT NULL REFERENCES kullanicilar(id),
    oturum_id       INTEGER NOT NULL REFERENCES oturumlar(id),
    katilma_zamani  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),

    PRIMARY KEY (kullanici_id, oturum_id)  -- bir öğrenci bir oturuma bir kez katılır
);


-- ---------------------------------------------------------------------
-- 6) CEVAPLAR: öğrencinin bir soruya verdiği cevap
-- ---------------------------------------------------------------------
CREATE TABLE cevaplar (
    id             INTEGER PRIMARY KEY,
    kullanici_id   INTEGER NOT NULL,
    oturum_id      INTEGER NOT NULL,
    soru_id        INTEGER NOT NULL,
    verilen_cevap  TEXT NOT NULL,
    cevap_zamani   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),

    CHECK (verilen_cevap IN ('A', 'B', 'C', 'D')),

    -- Her öğrencinin her sorudaki cevabı TEK satırdır.
    -- Cevap değişince yeni satır eklenmez, bu satır güncellenir.
    UNIQUE (kullanici_id, oturum_id, soru_id),

    -- Cevap veren, o oturuma katılmış olmalı (kullanıcı da var olmalı).
    FOREIGN KEY (kullanici_id, oturum_id)
        REFERENCES katilimlar(kullanici_id, oturum_id),

    -- Cevaplanan soru, GERÇEKTEN o oturumda olmalı.
    FOREIGN KEY (oturum_id, soru_id)
        REFERENCES oturum_sorulari(oturum_id, soru_id)
);


-- =====================================================================
-- İNDEKSLER
-- PRIMARY KEY ve UNIQUE sütunlarına SQLite kendisi indeks oluşturur.
-- Aşağıdakiler sık yapılan aramaları hızlandırmak için eklenmiştir.
-- =====================================================================

-- "Bu oturuma kimler katıldı?" (PK kullanici_id ile başladığı için ayrıca gerekli)
CREATE INDEX idx_katilimlar_oturum ON katilimlar(oturum_id);

-- Oturum ilerlemesi ve sonuç hesabı: cevapları oturum + soruya göre bulma
CREATE INDEX idx_cevaplar_oturum_soru ON cevaplar(oturum_id, soru_id);

-- "Bu soru hangi oturumlarda?" (PK oturum_id ile başladığı için ayrıca gerekli)
CREATE INDEX idx_oturum_sorulari_soru ON oturum_sorulari(soru_id);

-- Aktif oturumu bulma (durum = 'suruyor')
CREATE INDEX idx_oturumlar_durum ON oturumlar(durum);

-- KURAL: aynı anda yalnızca TEK bir oturum sürebilir.
-- Kısmi benzersiz indeks: UNIQUE kuralı sadece durum = 'suruyor' olan satırlara uygulanır.
-- 'baslamadi' ve 'bitti' durumunda istenildiği kadar oturum olabilir.
CREATE UNIQUE INDEX tek_aktif_oturum ON oturumlar(durum) WHERE durum = 'suruyor';


-- =====================================================================
-- TETİKLEYİCİLER (TRIGGER)
-- CHECK kısıtı yalnızca aynı satıra bakabilir. Başka tabloya bakan
-- ya da eski/yeni değeri karşılaştıran kurallar trigger ile yazılır.
-- =====================================================================

-- Oturum durumu yalnızca ileri gidebilir: baslamadi -> suruyor -> bitti
CREATE TRIGGER trg_oturum_durum_gecisi
BEFORE UPDATE OF durum ON oturumlar
WHEN NOT (
       NEW.durum = OLD.durum
    OR (OLD.durum = 'baslamadi' AND NEW.durum = 'suruyor')
    OR (OLD.durum = 'suruyor'   AND NEW.durum = 'bitti')
)
BEGIN
    SELECT RAISE(ABORT, 'Gecersiz durum gecisi (sira: baslamadi -> suruyor -> bitti)');
END;

-- Bitmiş bir oturuma katılım eklenemez
CREATE TRIGGER trg_katilim_bitmis_oturum
BEFORE INSERT ON katilimlar
WHEN (SELECT durum FROM oturumlar WHERE id = NEW.oturum_id) = 'bitti'
BEGIN
    SELECT RAISE(ABORT, 'Oturum bitmis: katilim eklenemez');
END;

-- Cevap yalnızca süren (aktif) oturuma eklenebilir
CREATE TRIGGER trg_cevap_ekle_aktif_oturum
BEFORE INSERT ON cevaplar
WHEN (SELECT durum FROM oturumlar WHERE id = NEW.oturum_id) <> 'suruyor'
BEGIN
    SELECT RAISE(ABORT, 'Oturum aktif degil: cevap kabul edilmez');
END;

-- Cevap yalnızca süren (aktif) oturumda değiştirilebilir
CREATE TRIGGER trg_cevap_guncelle_aktif_oturum
BEFORE UPDATE ON cevaplar
WHEN (SELECT durum FROM oturumlar WHERE id = NEW.oturum_id) <> 'suruyor'
BEGIN
    SELECT RAISE(ABORT, 'Oturum aktif degil: cevap degistirilemez');
END;


-- =====================================================================
-- GÖRÜNÜMLER (VIEW)
-- VIEW, kaydedilmiş bir SELECT sorgusudur, tablo gibi sorgulanır ama
-- veri saklamaz, her okunduğunda güncel veriden yeniden hesaplanır.
-- Puan ve süre gibi TÜRETİLEN bilgiler tablolarda saklanmaz, burada hesaplanır.
-- =====================================================================

-- Her oturumun durumu, geçen süresi ve 3 dakikayı aşan uzatma süresi.
-- strftime('%s', zaman) bir zamanı saniyeye çevirir, iki zamanın farkı = süre.
CREATE VIEW v_oturum_durumu AS
SELECT
    id, kod, baslik, hafta, durum, planlanan_sure_sn, baslangic, bitis,
    gecen_sure_sn,
    CASE WHEN gecen_sure_sn > planlanan_sure_sn
         THEN gecen_sure_sn - planlanan_sure_sn
         ELSE 0
    END AS uzatma_sn
FROM (
    SELECT
        oturumlar.*,
        CASE durum
            WHEN 'baslamadi' THEN NULL
            WHEN 'suruyor'   THEN strftime('%s', 'now', 'localtime') - strftime('%s', baslangic)
            ELSE                  strftime('%s', bitis)              - strftime('%s', baslangic)
        END AS gecen_sure_sn
    FROM oturumlar
);

-- PUANLAMA KURALI (tek yerde):
--   Her katılımcı için, katıldığı oturumda:
--   dogru  = doğru şıkkı seçtiği soru sayısı
--   yanlis = cevapladığı ama yanlış seçtiği soru sayısı
--   bos    = hiç cevaplamadığı soru sayısı
--   yuzde  = dogru / oturumdaki soru sayısı * 100   (yanlış ve boş = 0 puan)
CREATE VIEW v_sonuclar AS
SELECT
    oturum_id,
    kullanici_id,
    soru_sayisi,
    cevaplanan,
    dogru,
    cevaplanan - dogru               AS yanlis,
    soru_sayisi - cevaplanan         AS bos,
    ROUND(100.0 * dogru / soru_sayisi, 1) AS yuzde
FROM (
    SELECT
        k.oturum_id,
        k.kullanici_id,
        (SELECT COUNT(*) FROM oturum_sorulari os
          WHERE os.oturum_id = k.oturum_id)                          AS soru_sayisi,
        COUNT(c.id)                                                  AS cevaplanan,
        SUM(CASE WHEN c.verilen_cevap = s.dogru_cevap THEN 1 ELSE 0 END) AS dogru
    FROM katilimlar k
    LEFT JOIN cevaplar c ON c.kullanici_id = k.kullanici_id
                        AND c.oturum_id    = k.oturum_id
    LEFT JOIN sorular s  ON s.id = c.soru_id
    GROUP BY k.oturum_id, k.kullanici_id
);

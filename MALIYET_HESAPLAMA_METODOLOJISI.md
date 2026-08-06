# Araç Filosu Maliyet Hesaplama Metodolojisi

> Bu doküman, **ziraatfilo_maliyet** projesinde (ZiraatFilo için geliştirilen araç
> filosu maliyet analiz paneli) tasarlanıp uygulanmış olan **"bir aracın gerçekte
> kaça mal olduğunu" hesaplama sistemini** uçtan uca, formül formül belgeler.
>
> Amaç: bu mantığı **başka bir araç kiralama analiz uygulamasına** taşımak. O
> uygulama zaten piyasadaki (enuygun vb.) kiralama fiyatlarını çekip filo
> müdürüne gösteriyor — burada eksik olan parça, "bu aracı elimde tutmanın bana
> günlük/aylık/toplam maliyeti nedir" sorusuna gerçek muhasebe/finansman
> mantığıyla cevap veren bu sistem. Müdür, piyasa fiyatı ile kendi maliyetini
> yan yana görünce, aracı **hangi fiyatın altına kiraya vermemesi gerektiğini**
> (kurtaran fiyat) net biçimde anlayabilir.
>
> Doküman kasıtlı olarak çok detaylıdır — her formül, her edge-case, her
> tasarım kararının **NEDENİ** ile birlikte yazılmıştır ki başka bir projede
> bağlamı hiç bilmeyen biri (ya da bir LLM) bunu okuyup doğru şekilde
> uygulayabilsin.

---

## İçindekiler

1. [Genel Felsefe ve Temel Kavramlar](#1-genel-felsefe-ve-temel-kavramlar)
2. [Veri Modeli — Bir Aracın Maliyetini Hesaplamak İçin Neye İhtiyacınız Var](#2-veri-modeli)
3. [ÇEKİRDEK: Beş Maliyet Bileşeni](#3-çekirdek-beş-maliyet-bileşeni)
   - 3.1 [Kredi Faizi (Finansman — Kredili Kısım)](#31-kredi-faizi)
   - 3.2 [Nakit Fırsat Maliyeti (Finansman — Nakit/Özkaynak Kısım)](#32-nakit-fırsat-maliyeti)
   - 3.3 [Genel Gider Payı (Muhasebe/Overhead Dağıtımı)](#33-genel-gider-payı)
   - 3.4 [Sigorta / Kasko Maliyeti](#34-sigorta--kasko-maliyeti)
   - 3.5 [Operasyon Gideri](#35-operasyon-gideri)
   - 3.6 [Genel Toplam Maliyet](#36-genel-toplam-maliyet)
4. [Güncel Günlük Maliyet (Hibrit Oran) — "Bu araç bugün günde kaça mal oluyor?"](#4-güncel-günlük-maliyet-hibrit-oran)
5. [Zaman Serisi Kırılımı (Aylık/Günlük Dashboard Görünümü)](#5-zaman-serisi-kırılımı)
6. [Kaça Kiraya Vermeli? — Kurtaran Fiyat Hesabı](#6-kaça-kiraya-vermeli--kurtaran-fiyat-hesabı)
7. [OPSİYONEL: Kira Geliri/Kâr Simülasyonu](#7-opsiyonel-kira-geliri-kâr-simülasyonu)
8. [İLERİ SEVİYE / OPSİYONEL Senaryolar](#8-i̇leri-seviye--opsiyonel-senaryolar)
   - 8.1 [Senaryo 3 — Araç Satışından Elde Edilen Nakitle Yeni Araç Alımı](#81-senaryo-3)
   - 8.2 [Senaryo 4 — Araç Takas İşlemleri](#82-senaryo-4)
9. [Fiyat Tahmin Algoritması (Eksik/Güncel Piyasa Değeri Tahmini)](#9-fiyat-tahmin-algoritması)
10. [Genel Prensipler ve Tuzaklar Listesi](#10-genel-prensipler-ve-tuzaklar-listesi)
11. [Bu Projeye Özgü Olup PORTLANMAMASI Gereken Kısımlar](#11-bu-projeye-özgü-olup-portlanmaması-gereken-kısımlar)
12. [Entegrasyon Rehberi](#12-entegrasyon-rehberi)

---

## 1. Genel Felsefe ve Temel Kavramlar

### 1.1 Retroaktif ve Kümülatif Hesaplama İlkesi

Bu sistemdeki **her maliyet, ileriye dönük bir tahmin/bütçe DEĞİL, geçmişe
dönük ve kümülatiftir.** Yani "bu araç gelecek ay şu kadara mal olacak" değil,
"bu araç FİLOYA GİRDİĞİ GÜNDEN BUGÜNE KADAR toplam şu kadara mal oldu, ve şu an
günlük şu hızda maliyet biriktiriyor" sorusuna cevap verilir.

Bunun sonucu olarak, **her aracın kendi zaman ekseni farklıdır** — araç A 2021
sonunda filoya girmişse hesap 2021'den bugüne, araç B 2025'te girmişse
2025'ten bugüne yapılır. Filo genelinde tek bir "dönem" (örn. "2026 Q1") YOKTUR;
her aracın maliyeti kendi girişinden itibaren birikir.

**Neden bu şekilde tasarlandı:** Filo müdürünün ihtiyacı "bu aracı elimde
tutmanın bugüne kadar bana toplam neye mal olduğu" ve "şu an günlük ne hızda
maliyet biriktirdiği" bilgisidir — kiralama fiyatı kararı verirken geçmiş
performansı bilmek istiyor, hayali bir gelecek projeksiyonu değil.

### 1.2 Üç Zaman Ufku Kavramı

Finansman gideri gibi vadeli kalemlerde üç ayrı toplam hesaplanır:

| Kavram | Anlamı |
|---|---|
| **Vade Boyunca (Toplam)** | Kredinin/poliçenin TÜM vadesi boyunca ödenecek toplam tutar (geçmiş + gelecek) |
| **Bugüne Kadar (Tahakkuk Eden)** | Bugüne kadar geçen süre için tahakkuk etmiş kısım — asıl "gerçek maliyet" budur |
| **Kalan (Gelecek)** | Vade bitimine kadar kalan, henüz tahakkuk etmemiş kısım |

Dashboard'da ve "genel toplam maliyet" hesaplarında **HER ZAMAN "Bugüne Kadar"
kullanılır** — henüz gerçekleşmemiş gelecek taksitler asla bugünün maliyetine
dahil edilmez.

### 1.3 Kaynak Veri = Source of Truth İlkesi

Orijinal projede tüm hesaplamalar sıralı Python/pandas script'leriyle
(pipeline) yapılıp Excel dosyalarına yazılır; veritabanı sadece bu Excel'lerin
bire bir import edildiği bir **sunum katmanıdır** (hesaplama mantığı DB'de
YOKTUR, sadece "en son hesaplanmış sonuç" DB'de saklanır). Bu ayrım, hesaplama
mantığının test edilmesini/denetlenmesini kolaylaştırır (her adımın çıktısı
ayrı bir Excel dosyasında, elle incelenebilir).

**Başka bir projeye taşırken bu ayrımı birebir kopyalamak ZORUNLU değildir** —
asıl önemli olan burada anlatılan **hesaplama mantığı/formüllerdir**. Yeni
projede bu hesaplamalar doğrudan Django/başka bir backend'in servis
katmanında, gerçek zamanlı ya da günlük bir cron job ile yapılabilir. Önemli
olan, ilkenin korunması: "gerçek gider/finansman verisinden türetilmiş, tahmin
olmayan bir maliyet rakamı."

### 1.4 Gün Sayımı Kuralları (ÖNEMLİ — kolayca hatalı uygulanabilir)

Sistemde iki farklı gün sayımı kuralı bilinçli olarak bir arada kullanılır:

**a) Dönem ağırlıklandırma (start-exclusive, end-inclusive):**
Bir "dönem" (örn. bir kredi taksit dönemi), önceki taksit tarihinden
(dahil değil) bu taksitin tarihine (dahil) kadar olan aralıktır:

```
gün_sayısı = (dönem_bitiş − max(dönem_başlangıç, aracın_filoya_giriş_tarihi)).gün
```

`.dt.days` doğrudan fark alındığında zaten bu kuralı verir (başlangıç günü
sayılmaz, bitiş günü sayılır) — ekstra `+1` YAPILMAZ. Bu, ardışık dönemlerin
üst üste binmeden/gün kaybetmeden birbirini tam takip etmesini sağlar (dönem
N'nin bitiş günü = dönem N+1'in başlangıç günü, ama o gün sadece dönem N+1'e
sayılır).

**b) Aylık kova (bucket) gün sayımı (start-inclusive, end-inclusive):**
"Bu ay içinde araç kaç gün fiilen filoda/aktifti" sorusunda (örn. aylık kira
geliri simülasyonu, aylık dashboard kırılımı), hem ayın İLK günü hem SON günü
dahil edilir çünkü bu bir "içinde bulunma" sorgusudur, bir "dönem ağırlığı"
değil:

```python
def ay_ici_gun_sayisi(ay_baslangici, arac_giris_tarihi, bugun):
    ay_basi_dahil = max(ay_baslangici, arac_giris_tarihi)
    ay_sonu_dahil = min(ay_baslangici_bir_sonraki_ay - 1_gun, bugun)
    return (ay_sonu_dahil - ay_basi_dahil).gün + 1   # <-- burada +1 VAR
```

**KRİTİK TUZAK — bu projede gerçekten yaşanmış bir bug:** Bu fonksiyonun İKİ
UCU da (araç ay ortasında filoya girmişse VE bugün ayın ortasındaysa) kırpılmalı.
İlk uygulamada sadece "bugünün ayı" için kırpma yapılmış, aracın filoya girdiği
İLK ay için kırpma unutulmuştu — bu da aracın ilk (kısmi) ayında olduğundan
fazla gün sayılmasına, dolayısıyla o ayın maliyet/gelirinin fazla hesaplanmasına
yol açıyordu. Tek, simetrik bir `max(ay_başı, giriş_tarihi)` / `min(ay_sonu,
bugün)` kırpması her iki ucu da doğru ele alır — **iki ayrı özel-durum kodu
yazmak yerine tek bir simetrik formül kullanın.**

### 1.5 "Bilinmiyor" ≠ "Sıfır" İlkesi

Fiyatı/finansman bilgisi eksik olan bir araç için maliyet **0 olarak
YAZILMAZ** — açıkça `None`/`null` bırakılır ve arayüzde "Bilinmiyor (Veri
Eksik)" gibi ayrı bir durum olarak gösterilir. Aksi halde ortalama/toplam
hesaplarında sessizce yanlış (düşük) sonuçlar üretilir. Bu ayrım tüm
hesaplamalarda tutarlı biçimde korunmalıdır.

---

## 2. Veri Modeli

Bir aracın tam maliyetini hesaplayabilmek için minimum şu veriler gerekir:

| Veri | Kullanıldığı Bileşen |
|---|---|
| Araç kimliği (şasi no / plaka), **filoya giriş tarihi**, satın alım fiyatı | Hepsi — zaman ekseni ve fiyat-ağırlıklı dağıtımların temeli |
| Finansman tipi: **Nakit / Kredi / Karma** + karma ise kırılım oranı | §3.1, §3.2 |
| Krediliyse: bağlı olduğu kredi(ler), her kredinin tutarı/faiz oranı/vadesi/taksit planı | §3.1 |
| Nakit kısmı varsa: nakit ile finanse edilen tutar | §3.2 |
| Genel şirket giderleri (personel, kira, elektrik vb. — araca özel olmayan), günlük/aylık toplam tutar | §3.3 |
| Sigorta/Kasko poliçeleri: tip, tutar, başlangıç/bitiş tarihi | §3.4 |
| Araca özel işlem giderleri (bakım, lastik, hasar, yakıt vb.), her biri tarihli ve tutarlı | §3.5 |

**Önemli:** Bu projede finansman tipi ve bazı poliçe/gider verileri gerçek veri
eksikliği yüzünden **sentetik üretilmiştir** (bkz. §11). Hedef projede bu
alanların GERÇEK verisi zaten mevcutsa (örn. FYS/muhasebe sisteminden), o
gerçek veriyi doğrudan kullanın — sentetik üretim mantığını KOPYALAMAYIN.

---

## 3. ÇEKİRDEK: Beş Maliyet Bileşeni

Bir aracın toplam maliyeti tam olarak şu 5 bileşenin toplamıdır. Hiçbiri
tahmin/varsayım değildir (finansman tipi/tutarları gerçek veri olduğu sürece)
— hepsi gerçek kredi/poliçe/gider kayıtlarından matematiksel olarak türetilir.

### 3.1 Kredi Faizi

**Girdi:** Aracın bağlı olduğu bir veya daha fazla kredi; her kredinin
tutarı (`P`), aylık faiz oranı (`r`), vadesi ay cinsinden (`n`), başlangıç
tarihi.

**Adım 1 — Standart Anüite (Eşit Taksitli Amortisman) Formülü:**

```
Sabit Taksit Tutarı = P × r / (1 − (1 + r)^−n)
```

Her ay için (azalan bakiye yöntemi):

```
Faiz Tutarı(ay)  = Kalan Anapara × r
BSMV(ay)         = Faiz Tutarı(ay) × %5        ← Türkiye'ye özgü banka/sigorta işlem vergisi
Anapara(ay)      = Sabit Taksit Tutarı − Faiz Tutarı(ay) − BSMV(ay)
Kalan Anapara    -= Anapara(ay)                 (bir sonraki ay için)
```

Son taksitte yuvarlama farkını temizlemek için `Anapara = Kalan Anapara`
(kalanın tamamı) yazılır ve o ayın taksit tutarı buna göre yeniden hesaplanır
— aksi halde kalan anapara asla tam sıfıra inmez.

> **NOT (BSMV):** Bu, Türkiye'deki banka/finans kredilerinde faiz üzerinden
> alınan bir vergidir (~%5, örnek taksit tablosundan ampirik doğrulandı).
> Türkiye dışında bir pazar için bu satırı kaldırın ya da o ülkenin eşdeğer
> vergisiyle değiştirin. Türkiye pazarındaysanız muhtemelen aynen geçerlidir.

**Adım 2 — Bir Araç Birden Fazla Krediye/Bir Kredi Birden Fazla Araca
Bağlıysa: Ağırlıklı Dağıtım.**

Gerçek hayatta bir kredi birden fazla aracı finanse edebilir (ya da bir araç
kısmen birden fazla krediyle finanse edilmiş olabilir — "karma" finansman).
Bu durumda her taksit döneminde, o krediye bağlı TÜM araçlara **ağırlıklı**
dağıtım yapılır:

```
Dönem: bir önceki taksit tarihinden (dahil değil) bu taksitin tarihine (dahil) kadar

ağırlık(araç, dönem) = araç_kredi_ile_finanse_edilen_tutar × dönem_içindeki_gün_sayısı
   (NOT: aracın TAM fiyatı değil, sadece KREDİYLE finanse edilen kısmı —
    karma finansmanlı bir araç kendi payından fazla kredi maliyeti yüklenmemeli)

pay(araç, dönem) = ağırlık(araç, dönem) / Σ(dönemdeki tüm araçların ağırlığı) × dönemin_taksit_tutarı

günlük(araç, dönem) = pay(araç, dönem) / 30   ← basitleştirme: takvim ayı yerine sabit 30 gün varsayılır
```

Eğer araç dönem içinde sonradan filoya girmişse (dönem başlangıcından SONRA),
`gün_sayısı` sadece filoya giriş tarihinden itibaren sayılır:
`overlap_start = max(dönem_başlangıç, araç_filoya_giriş_tarihi)`.

**Doğrulama (mutlaka uygulayın):** Her kredi için, tüm araçlara dağıtılan
toplam tutar = kredinin taksit tutarları toplamına eşit olmalıdır (yuvarlama
farkı hariç, ~0.0001 TL mertebesinde). Eğer bir döneme bağlı hiçbir araç yoksa
(örn. kredi tüm araçları kapsamıyorsa) o dönem dağıtılamaz — bu normal bir
durumdur, ama miktarı raporlanmalı ("dağıtılamayan tutar").

**Bugüne kadar tahakkuk eden kredi faizi** = taksit tarihi ≤ bugün olan tüm
dönemlerin payları toplamı. **Kalan** = taksit tarihi > bugün olanlar.

### 3.2 Nakit Fırsat Maliyeti

Nakit (özkaynak) ile finanse edilen araçlar için, kullanılan sermayenin
**alternatif maliyeti** (o parayı bankaya yatırsaydı kazanılacak faiz)
maliyete yazılır. Krediye paralel olarak (kredi kendi taksit vadesiyle
kendiliğinden bittiği gibi) **bunun da bir vadesi vardır** — şirket
ayarındaki varsayılan süre (`cash_opportunity_term_months`, filoya giriş
tarihinden itibaren) dolunca fırsat maliyeti durur, araç filoda kalmaya
devam etse bile:

Getiri, Türkiye'deki standart mevduat faizi kuralıyla hesaplanır — gün
sayısı, artık yıl olmayan yıllarda 365, artık yıllarda (2020, 2024, 2028
gibi 4'e bölünebilen yıllar) 366 üzerinden hesaplanır:

```
Artık olmayan yıllar için: Getiri = (Anapara × Faiz Oranı × Gün Sayısı) / 36500
Artık yıllar için:         Getiri = (Anapara × Faiz Oranı × Gün Sayısı) / 36600

Günlük Fırsat Maliyeti = Nakit ile Finanse Edilen Tutar × (Yıllık Mevduat Faiz Oranı / (365 veya 366))
                        = 0                                    eğer bugün ≥ vade_tarihi
Vade Tarihi             = filoya_giriş_tarihi + Nakit Fırsat Maliyeti Vadesi (ay)
```

Bölen, hesaplanan günün AİT OLDUĞU takvim yılına göre seçilir. Bir dönem
(ör. "bugüne kadar tahakkuk eden") birden fazla takvim yılına yayılıyorsa —
mesela filoya giriş 2020'de, bugün 2023'te ise — dönem takvim yılı
sınırlarında bölünür, her yılın kendi payı o yılın kendi böleniyle (365 ya
da 366) ayrı ayrı hesaplanıp toplanır. Tek bir "sabit günlük oran × toplam
gün" çarpımı YETERLİ DEĞİLDİR, çünkü yıllar arası bölen değişebilir.

Bu projede **Yıllık Mevduat Faiz Oranı = %40**, **Nakit Fırsat Maliyeti
Vadesi = 36 ay (3 yıl)** olarak kullanıcıyla birlikte sabit varsayılmıştır
(ikisi de **gerçek/güncel piyasa oranı/iş kararıyla değiştirilebilir**,
şirket başına `CostCalculationSettings` üzerinden). Karma finansmanlı
araçlarda sadece nakit kısmına uygulanır (kredi kısmı zaten §3.1'de ayrıca
hesaplanır).

### 3.3 Genel Gider Payı

Şirketin araca özel OLMAYAN genel giderleri (personel maaşları, kira,
elektrik, danışmanlık vb.) filodaki TÜM araçlara **fiyat-ağırlıklı** olarak
günlük bazda dağıtılır:

```
Her gün için:
  filodaki_araçlar = o gün itibarıyla filoya girmiş olan (giriş_tarihi ≤ o_gün) tüm araçlar
  pay(araç, gün) = araç_fiyatı / Σ(filodaki_tüm_araçların_fiyatı) × o_günün_toplam_genel_gideri
```

Şube/lokasyon ayrımı yapılmaz — tüm şubelerin toplam günlük genel gideri tek
bir havuzda toplanıp fiyat ağırlığıyla dağıtılır. Bu bileşen finansman
maliyetinin bir alt kalemi olarak ele alınmıştır (toplam finansman maliyetine
eklenir), ama isterseniz ayrı bir "genel gider" kalemi olarak da
sunabilirsiniz — matematiksel olarak fark etmez, sadece raporlama tercihi.

**Neden fiyat ağırlıklı?** Daha pahalı bir aracın sermaye/amortisman yükü
daha yüksek olduğu için, genel işletme giderlerinden de orantılı olarak daha
fazla pay alması makul kabul edilmiştir (kullanıcıyla netleştirilen iş kararı
— alternatif olarak eşit dağıtım ya da km-bazlı dağıtım da tercih edilebilir,
bu bir iş kararıdır, matematiksel bir zorunluluk değil).

### 3.4 Sigorta / Kasko Maliyeti

Her poliçe (Trafik, Kasko, Yeşil Kart vb.) TEK bir araca ait, havuzlu dağıtım
YOKTUR. Poliçeler tipik olarak 1 yıllık ve tek seferde peşin ödenmiş kabul
edilir:

```
Günlük Maliyet = Poliçe Tutarı / 365
Bugüne Kadar Tahakkuk Eden = Günlük Maliyet × (bugün − poliçe_başlangıç_tarihi).gün
Kalan (Yenilemeye Kadar) = Günlük Maliyet × (poliçe_bitiş_tarihi − bugün).gün
```

Bir araç birden fazla poliçe tipine (Trafik + Kasko + Yeşil Kart) sahip
olabilir — bunların toplamı aracın sigorta maliyetidir.

**Poliçe süresi dolmuş ama yeni poliçe kaydı henüz girilmemişse** ne
yapılacağına dikkat edin — bu projede (§4'te detaylandırılan güncel günlük
maliyet hesabında) "en son bilinen poliçe aynı günlük oranla YENİLENMİŞ"
varsayılır, sigorta maliyeti aniden sıfıra düşmez.

### 3.5 Operasyon Gideri

Bakım, lastik değişimi, hasar onarımı, yıkama, muayene gibi **doğrudan
belirli bir araca ve tarihe bağlı** giderlerdir. Kredi/genel gider gibi
ağırlıklı dağıtıma HİÇ gerek yoktur — her muhasebe kaydı zaten kendi tarihinde
kendi aracına yazılıdır, olduğu gibi toplanır:

```
Aracın Toplam Operasyon Gideri = Σ(o araca ait tüm işlem kayıtlarının net tutarı)
```

Muhasebe kategorilerini (hesap adı) daha okunabilir "alt kalem" gruplarına
eşlemek faydalıdır (örn. "ARAÇ LASTİK GİDERLERİ" → "Lastik İşlemleri", "ARAÇ
YIKAMA GİDERLERİ" → "Standart Yıkama") — bu tamamen görsel/raporlama amaçlı bir
eşleme, hesaba etkisi yoktur. Eşlenemeyen kategoriler "Diğer (Eşlenmemiş)"
altına düşürülüp gözden geçirilmelidir.

### 3.6 Genel Toplam Maliyet

```
Genel Toplam Maliyet = Kredi Faizi (Bugüne Kadar)
                      + Nakit Fırsat Maliyeti (Bugüne Kadar)
                      + Genel Gider Payı (Bugüne Kadar)
                      + Sigorta/Kasko Maliyeti (Bugüne Kadar)
                      + Operasyon Gideri (Toplam)
```

Bu, "bu araç bugüne kadar bana toplam ne kadara mal oldu" sorusunun tam
cevabıdır. Finansmanı "Bilinmiyor" olan araçlar (fiyat eksikse) bu toplamdan
hariç tutulur veya ayrı işaretlenir — §1.5'e bakınız.

---

## 4. Güncel Günlük Maliyet (Hibrit Oran)

Filo müdürü için asıl kritik rakam genelde şudur: **"bu araç ŞU AN, bugün
itibarıyla, günde/ayda ne kadara mal oluyor?"** — bu, kiralama fiyatı
belirlerken kullanılacak "kurtaran fiyat" tabanıdır (bkz. §6).

Bu, "Bugüne Kadarki Toplam / Geçen Gün Sayısı" gibi basit bir ortalama
DEĞİLDİR — çünkü finansman/sigorta gibi bileşenlerin GÜNCEL/MARJİNAL oranı
(şu anki taksit/poliçe oranı), geçmiş ortalamadan farklı olabilir (örn. kredi
azalan bakiyeli olduğu için taksitin faiz kısmı zamanla küçülür — ilk yılın
ortalaması ile bugünkü marjinal oran aynı değildir). Bu yüzden **hibrit** bir
yaklaşım kullanılır — bileşene göre iki farklı yöntem karışık uygulanır:

| Bileşen | Yöntem | Neden |
|---|---|---|
| **Kredi** | GÜNCEL/MARJİNAL: bugünden sonraki İLK gelecek taksitin günlük tutarı | Taksitler zamanla değiştiği (azalan bakiye) için "şu an" doğru oran budur |
| **Nakit Fırsat Maliyeti** | GÜNCEL/MARJİNAL: zaten sabit oran (tutar × yıllık_oran/365) — zamanla değişmez | Sabit oranlı bir kalem, ortalamaya gerek yok |
| **Sigorta/Kasko** | GÜNCEL/MARJİNAL: bugün itibarıyla aktif olan poliçenin günlük maliyeti | Poliçe yıllık sabit tutarlı, "şu an" oranı zaten net |
| **Genel Gider Payı** | ORTALAMA: bugüne kadarki toplam / filoya giriş tarihinden bugüne geçen gün sayısı | Bu kalemin "güncel taksiti" kavramı yok (tek seferlik/kümülatif bir pay), tarihi ortalama kullanılır |
| **Operasyon** | ORTALAMA: bugüne kadarki toplam / filoya giriş tarihinden bugüne geçen gün sayısı | Aynı sebep — düzensiz aralıklarla gerçekleşen kalemler için "güncel oran" kavramı anlamsız |

```
Güncel Günlük Maliyet = Kredi_Günlük(marjinal)
                       + Nakit_Fırsat_Günlük(sabit)
                       + Sigorta_Günlük(marjinal, aktif poliçe)
                       + Genel_Gider_Günlük(ortalama, bugüne_kadar/gün_sayısı)
                       + Operasyon_Günlük(ortalama, bugüne_kadar/gün_sayısı)
```

**Kredi için "gelecek ilk taksit" bulma detayı:** Araç birden fazla krediye
bağlıysa, HER kredi için ayrı ayrı "bugünden sonraki ilk taksit"i bulup
günlük tutarlarını toplayın (bir krediyi atlamayın). Verimlilik için: tüm
gelecek taksitleri kredi no + taksit tarihine göre sıralı tek bir sorguda
çekip, her kredi için görülen İLK (en yakın) satırı alın — araç başına kredi
sayısı kadar ayrı sorgu atmaktan kaçının (N+1 query problemi).

---

## 5. Zaman Serisi Kırılımı

Dashboard'da "Genel Toplam Maliyet"in aylık ya da günlük kırılımını göstermek
için (örn. bir çubuk/alan grafiği), her maliyet bileşeni **kendi gerçek
tahakkuk mantığına göre** bir zaman dilimine (ay veya gün) atanır:

- **Kredi:** taksit tarihine göre — o taksitin ait olduğu ay/gün.
- **Nakit Fırsat Maliyeti:** SÜREKLİ günlük tahakkuk — aracın filoya giriş
  tarihinden bugüne kadar HER gün için sabit bir günlük tutar.
- **Genel Gider Payı:** zaten günlük olarak hesaplandığı için (§3.3) direkt
  o günün/ayın kovasına eklenir.
- **Sigorta:** SÜREKLİ günlük tahakkuk — poliçe başlangıcından
  min(bitiş, bugün)'e kadar her gün için sabit günlük oran.
- **Operasyon:** işlem tarihine göre — zaten günlük kayıtlar.

**Pratik detay — "Bu Dönemden Önce" kovası:** Filoya giriş tarihi gibi
alanlarda hatalı/placeholder veri (örn. 1970-01-01 epoch değeri) olma
ihtimaline karşı, aylık görünüm SADECE son N ayı (örn. son 24 ay) tek tek
gösterir; daha eskisi tek bir "Bu Dönemden Önce" kalemine toplanır. Toplam
hiçbir zaman kaybolmaz, sadece görünümde gruplanır — bu sayede anormal derecede
eski/hatalı bir tarih grafiği bozmaz.

---

## 6. Kaça Kiraya Vermeli? — Kurtaran Fiyat Hesabı

Bu, projenin nihai iş amacıdır ve diğer projedeki entegrasyonun asıl
motivasyonudur. Mantık şu şekilde kurulabilir:

```
Günlük Kurtaran Fiyat = Güncel Günlük Maliyet (§4) × (1 + Hedef Kâr Marjı)
```

Burada `Hedef Kâr Marjı`, şirketin belirlediği bir iş kararıdır (örn. %15-20).
Bu projede kira geliri simülasyonunda kullanılan hedef %20'dir (bkz. §7), ama
bu tamamen değiştirilebilir bir parametredir.

**Doluluk oranı düzeltmesi (önemli, aksi halde yanıltıcı olabilir):** Eğer
araç her gün kirada olmuyorsa (örn. %60 doluluk oranıyla çalışıyorsa),
sadece kirada olunan günlerin geliriyle boşta geçen günlerin maliyetini de
karşılamak gerekir. Aksi halde sabit bir kâr marjı, düşük dolulukta
MATEMATİKSEL OLARAK KAÇINILMAZ ZARARA yol açar (boşta geçen günün maliyeti
hiçbir zaman telafi edilmez). Bu proje bu sorunu şu formülle çözer:

```
Çarpan = (1 + Hedef Kâr Marjı) / Doluluk Oranı

Kirada Olunan Günün Kurtaran Fiyatı = Güncel Günlük Maliyet × Çarpan
```

Örnek: %20 hedef kâr, %50 doluluk oranı → çarpan = 1.20 / 0.50 = **2.40**
— yani kirada olduğu her gün, o günün maliyetinin **%140 fazlasını**
karşılayacak bir fiyattan kiraya verilmelidir ki boşta geçen günler de dahil
toplamda %20 net kâr hedefine ulaşılsın. %100 doluluk oranında (sürekli
kirada) çarpan sadece 1.20'dir (kirada geçen her gün zaten maliyetin sadece
%20 fazlasını karşılaması yeterlidir, çünkü boşta gün yoktur).

**Bu, diğer projede muhtemelen EN DEĞERLİ formüldür** — çünkü o proje zaten
gerçek rezervasyon/doluluk verisine sahip (rezervasyonları kontrol ediyor).
Aracın GERÇEK geçmiş doluluk oranını (kirada geçen gün / toplam gün) hesaplayıp
bu formüle koyarak, her araç için "bu doluluk oranıyla çalışırsam kârda kalmak
için minimum günlük X TL'nin altına inmemeliyim" rakamını doğrudan
üretebilirsiniz.

---

## 7. OPSİYONEL: Kira Geliri/Kâr Simülasyonu

> **Bu bölüm muhtemelen diğer projede GEREKLİ DEĞİLDİR** çünkü o proje zaten
> gerçek rezervasyon/kiralama verisine sahip — gerçek geliri gerçek
> rezervasyonlardan hesaplayabilirsiniz, simülasyona gerek yok. Yine de
> §6'daki doluluk-düzeltmeli kâr marjı formülünün NEREDEN geldiğini anlamak
> için referans olarak bırakılmıştır.

ZiraatFilo projesinde henüz gerçek kiralama/gelir verisi entegre
edilemediğinden (FYS entegrasyonu bekleniyor), "Genel Toplam Maliyet" ile
aynı zaman ekseninde SİMÜLE EDİLMİŞ bir gelir katmanı kurulmuştur. Üç havuza
ayrılır (gerçek bir "Aktif Sözleşme" alanının dolu/boş olmasına göre):

- **Sözleşmeli** (somut bir kurumsal sözleşmesi var): sürekli kirada kabul
  edilir, doluluk = %100, çarpan = 1.20.
- **Rotasyonlu** (kısa dönem havuzunda ama sözleşmesiz): 6 ayda bir yeniden
  karılan iki gruba (A/B) bölünüp aylık dönüşümlü olarak yarı zaman kirada
  kabul edilir, doluluk = %50, çarpan = 2.40.
- **Boşta** (uzun dönem havuzunda ama sözleşmesiz): hiçbir zaman kirada
  sayılmaz, gelir her zaman 0, ama maliyet birikmeye devam eder (net
  zarar kalemi olarak görünür — gerçekçi: atıl bir aracın geliri olmaz).

```
Aylık Gelir = (o ayki toplam günlük maliyet × o ayki gün sayısı × çarpan)   eğer kirada ise
            = 0                                                              eğer boşta ise
```

Filo genelindeki BLENDED (harmanlanmış) kâr oranı, "Boşta" havuzunun
gelirsiz maliyeti yüzünden hedeften (%20) daha düşük çıkar — bu beklenen ve
doğru bir sonuçtur, hata değildir.

**Gerçek veriyle port ederken:** `kirada_mi` alanını simülasyondan değil
GERÇEK rezervasyon tablosundan türetin (o gün/ay için o araca ait aktif bir
rezervasyon var mı), `aylik_gelir`i de simülasyon formülünden değil GERÇEK
tahsil edilen kira tutarından alın. §6'daki kurtaran-fiyat formülü, ancak bu
gerçek veriyle "olması gereken minimum fiyat" ile "gerçekte alınan fiyat"ı
karşılaştırmak için kullanılabilir hale gelir — asıl değerli olan budur.

---

## 8. İLERİ SEVİYE / OPSİYONEL Senaryolar

Bu iki senaryo, filo yönetiminde araç DEĞİŞİMİ (satış→alım ya da takas)
sırasında finansman sürekliliğini/maliyet devrini modellemek için
eklenmiştir. Diğer projede filo değişimi/araç yenileme akışı varsa faydalı
olabilir; yoksa şimdilik atlanabilir.

### 8.1 Senaryo 3

**Bağlam:** Araç A satılır, elde edilen nakitle (+ gerekirse ek finansman ile)
yeni araç B alınır. B'nin toplam finansman maliyeti iki parçaya ayrılır:

- **Devredilen Kısım** = `min(B fiyatı, A satış geliri)` — bu kısım HER ZAMAN
  (gap olsun olmasın) sanki yeni bir kredi açılmış gibi muamele görür:
  şirketin ortalama kredi faiz oranıyla, standart bir vade (örn. 36 ay)
  üzerinden **azalan bakiyeli amortisman tablosu** kurulur (§3.1'deki
  formülün birebir aynısı, "hayali" bir kredi olarak). Anapara + Faiz + BSMV
  toplamının TAMAMI maliyete yazılır — tutarlılık için (bir aracın maliyeti
  asla "mahsup sonrası sıfıra yakın" gösterilmemeli, her araç karşılaştırılabilir
  kalmalı).
- **Gap** = `max(0, B fiyatı − A satış geliri)` — gerçekten YENİ finansman
  ihtiyacı, rastgele/iş kararına göre Kredi ya da Nakit ile kapatılır (Kredi
  ise yine azalan bakiyeli hayali kredi; Nakit ise §3.2'deki sabit günlük
  fırsat maliyeti oranı).

**Bekleme geliri ve mahsup:** A satıldıktan B alınana kadar geçen sürede,
elde bekleyen "A satış geliri" mevduat faiziyle gelir kazanır (bekleme_geliri
= satış_geliri × yıllık_mevduat_oranı/365 × bekleme_günü). Bu gelirin nereye
gideceği A'nın kredi durumuna bağlıdır:

- A'nın kredisi zaten bitmiş/hiç yoksa → bekleme geliri, Gap'in **sadece
  faiz+BSMV kısmından** (anaparadan DEĞİL) mahsup edilir; Gap yoksa ya da
  gelir mahsuptan fazlaysa taşan kısım "Diğer Gelir" olarak ayrı kaydedilir
  (hiçbir aracın maliyetine dokunmaz).
- A'nın kredisi hâlâ aktifse → bekleme geliri, A'nın GERÇEK kredisinin
  bekleme dönemiyle örtüşen taksit dönemlerindeki gerçek faiz+BSMV'sinden
  (gün bazında orantılı örtüşme payıyla) mahsup edilir; Gap'in maliyeti bu
  durumda mahsupsuz tam uygulanır.

**Devredilen kısmın hayali maliyetine hiçbir zaman mahsup uygulanmaz** —
mahsup kuralı sadece Gap'in faiz+BSMV'sine ilişkindir.

### 8.2 Senaryo 4

**Bağlam:** Araç A, araç B ile ANLIK takas edilir (aynı gün el değiştirir) —
bu yüzden Senaryo 3'teki bekleme dönemi/bekleme geliri/mahsup kavramları
YOKTUR. Bunun yerine **süreklilik** ilkesi uygulanır:

- A bir krediye bağlıysa (ve hâlâ aktifse): kredi bağlantısı DOĞRUDAN B'ye
  devredilir. Sıfırdan hayali bir kredi KURULMAZ — A'nın zaten gerçek, zaten
  azalan bakiyeli çalışan kredi payı, takas tarihinden itibaren B üzerinden
  devam eder (§3.1'deki ağırlıklı dağıtım mekanizması, A'nın ağırlığı takas
  tarihinden sonra sıfırlanıp B'ye aktarılmış haliyle yeniden çalıştırılır).
- A nakit finanse edilmişse (ya da kredisi bitmişse): A'nın nakit tutarı ve
  fırsat maliyeti hesabı aynen B'ye devreder, takas tarihinden itibaren.
- **Fiyat Farkı** (`Fark = B fiyatı − A'nın takas değeri`) imzalıdır: B daha
  pahalıysa Fark pozitiftir ve Senaryo 3'teki gap mantığıyla (rastgele
  kredi/nakit, düz oran×gün) B'nin üzerine ek finansman maliyeti olarak
  yazılır. A'nın takas değeri B'den pahalıysa Fark negatiftir — bu durumda
  B için bir finansman maliyeti DEĞİL, tek seferlik düz bir GELİR kalemi
  olarak ayrıca kaydedilir.

**A'nın Takas Değeri nasıl hesaplanır (önemli genel prensip):** A'nın kendi
ESKİ nominal alım fiyatının basit bir amortismanı OLARAK DEĞİL, §9'daki fiyat
tahmin algoritmasıyla bulunan GÜNCEL karşılaştırılabilir piyasa fiyatı
üzerine %70-95 aralığında bir amortisman uygulanarak hesaplanır. **Neden:**
yüksek enflasyon ortamında (örn. Türkiye), bir aracın yıllar önceki nominal
alım fiyatı üzerinden amortisman hesaplamak günümüz takas değerini ciddi
şekilde eksik gösterir — baz olarak her zaman GÜNCEL piyasa fiyatı
kullanılmalıdır. **Bu prensip, diğer projedeki enuygun'dan çekilen güncel
piyasa fiyatlarıyla doğrudan örtüşür** — zaten elinizde güncel piyasa
verisi varsa, tam da bu iş için kullanılabilir.

---

## 9. Fiyat Tahmin Algoritması

Hem eksik satın alım fiyatını doldurmak (bkz. §2) hem de bir aracın GÜNCEL
piyasa değerini tahmin etmek (bkz. §8.2) için aynı **kademeli (cascading)
eşleşme algoritması** kullanılır — en spesifik gruptan en genele doğru:

```
1) Aynı Marka + Model + Yıl grubundaki karşılaştırılabilir araçların ortalaması
2) (1. kademe boşsa) Aynı Marka + Model grubunun ortalaması (yıl fark etmeksizin)
3) (2. kademe boşsa) Aynı Segment/SIPP kodu grubunun ortalaması
4) (3. kademe boşsa, son çare) Aynı Marka grubunun ortalaması
```

Güncel piyasa değeri tahmininde, karşılaştırma havuzu ayrıca **sadece son 1
yıl içinde filoya girmiş VE gerçek (tahmin değil) fiyatlı** araçlarla
sınırlandırılır — böylece tahmin, eski/güncelliğini yitirmiş fiyatlardan değil
güncel piyasa koşullarından türetilir.

Hangi kademeden dolduğu her zaman ayrı bir "Fiyat Kaynağı" alanında
işaretlenir (şeffaflık için — "gerçek" veri ile "tahmini" veriyi asla
karıştırmayın, raporlarda ayrıştırılabilir olmalı).

**Bu algoritma diğer projede doğrudan kullanılabilir:** eğer filodaki bazı
araçların satın alım fiyatı eksikse ya da bir aracın "bugünkü karşılığı ne
kadar eder" bilgisine ihtiyacınız varsa (örn. amortisman, sigorta değeri,
takas/yenileme kararları için), bu kademeli algoritma - özellikle enuygun'dan
çekilen güncel piyasa verisiyle birleştirildiğinde - doğrudan port edilebilir.

---

## 10. Genel Prensipler ve Tuzaklar Listesi

Bu proje boyunca karşılaşılan ve düzeltilen gerçek hatalardan çıkarılan
dersler — port ederken aynı hatalara düşmemek için:

1. **Gün sayımı simetrik olmalı** (bkz. §1.4) — sadece "bugünün ayı" için
   özel durum yazıp aracın filoya girdiği ilk (kısmi) ay için unutmak, o ayın
   maliyetini/gelirini fazla hesaplamaya yol açar. Tek bir `max(...)`/`min(...)`
   kırpma formülü her iki ucu da kapsamalı.
2. **"Bilinmiyor" ile "sıfır"ı asla karıştırmayın** (bkz. §1.5) — eksik veri
   sessizce 0 yazılırsa toplam/ortalama hesapları yanlış (düşük) çıkar.
3. **Ağırlıklı dağıtımda TAM FİYAT değil, o bileşene ait GERÇEK PAYI kullanın**
   (örn. kredi dağıtımında aracın tam fiyatı değil, sadece kredi ile finanse
   edilen kısmı) — aksi halde karma finansmanlı bir araç kendi payından fazla
   maliyet yüklenir.
4. **Mahsup/indirim uygulanan kalemlerde SADECE ilgili bileşene** (örn. sadece
   faiz+BSMV'ye) uygulayın, anaparaya asla dokunmayın — anapara her zaman
   gerçek bir borç geri ödemesidir, indirime konu edilemez.
5. **Doğrulama adımını atlamayın:** her ağırlıklı dağıtım sonrası, dağıtılan
   toplamın kaynak toplama (örn. taksit tutarları toplamı) eşit olup
   olmadığını kontrol edin. Fark varsa ya yuvarlama hatasıdır (kabul
   edilebilir, ~0.0001 mertebesinde) ya da mantık hatasıdır (araştırılmalı).
6. **Sabit kâr marjı + değişken doluluk oranı = matematiksel olarak kaçınılmaz
   zarar riski** (bkz. §6) — düşük dolulukta çalışan bir filo segmentinde
   kâr hedefine ulaşmak istiyorsanız marjı doluluk oranına göre
   `(1+hedef)/doluluk` şeklinde düzeltin, sabit bırakmayın.
7. **Retroaktif/kümülatif ile ileriye dönük projeksiyonu karıştırmayın**
   (bkz. §1.1) — bu sistemin tamamı geçmişe bakar, "olacak" değil "oldu" ve
   "şu an ne hızda oluyor" sorularına cevap verir.
8. **Her aracın kendi zaman ekseni var** — filo genelinde tek bir ortak
   "dönem" yoktur, her hesap aracın kendi filoya giriş tarihinden bugüne
   yapılır.

---

## 11. Bu Projeye Özgü Olup PORTLANMAMASI Gereken Kısımlar

ZiraatFilo projesinde bazı girdi verileri (henüz gerçek entegrasyon
olmadığı için) **sentetik/test amaçlı üretilmiştir**. Bu üretim mantığı
sadece test verisi doldurmak içindir — **hedef projede karşılık gelen GERÇEK
veri varsa bu kısımları KOPYALAMAYIN, doğrudan gerçek veriyi kullanın:**

- **Finansman Tipi (Nakit/Kredi/Karma) atanması:** bu projede her araca
  rastgele %35 Nakit / %50 Kredi / %15 Karma olasılıkla sentetik atanmıştır
  (gerçek sistemde bu alan elle/muhasebe sisteminden girilecek bir alandır).
- **Kredi-araç eşleştirmesi:** hangi kredinin hangi araçları finanse ettiği
  bu projede rastgele (ama tutarlı, sabit seed'li) atanmıştır — gerçek
  projede bu gerçek bir kredi tahsis kaydı olmalıdır.
- **Sigorta poliçeleri:** kapsama oranları (%97 Trafik, %90 Kasko, %10 Yeşil
  Kart) ve tutar aralıkları (fiyatın %1-2'si, %4-7'si vb.) bu projede
  sentetik varsayımlardır — gerçek poliçe verisi varsa doğrudan kullanılmalı.
  Sadece **hesaplama formülü** (`günlük = poliçe_tutarı/365` vb.) evrenseldir.
- **Genel şirket giderlerinin anonimleştirilip ölçeklenmesi:** ZiraatFilo'nun
  gerçek ~22.000 araçlık filosundan alınan gerçek muhasebe verisinin, bu
  projenin küçük (1595 araçlık) test evrenine ölçeklenip anonimleştirilmesi
  tamamen bu projeye özgü bir veri hazırlama adımıdır (KVKK/gizlilik amaçlı).
  Gerçek projede muhasebe verisi zaten doğru ölçekte ve gerçek olacağı için bu
  adıma hiç gerek yoktur.
- **Satış zinciri/takas senaryolarındaki rastgele olay üretimi** (§8) — hangi
  araçların satıldığı/takas edildiği bu projede rastgele seçilip demo
  amaçlı üretilmiştir. Gerçek projede bu, gerçek satış/takas kayıtlarından
  gelmelidir; sadece **hesaplama mantığı** (devredilen kısım, gap, mahsup
  kuralları) evrenseldir.

**Kısacası:** Bu dokümanın §3, §4, §6, §9 ve §10 bölümleri — yani asıl
**hesaplama formülleri** — evrensel ve doğrudan portlanabilir. §7 ve §8
opsiyonel/ileri seviyedir. Yukarıdaki sentetik veri ÜRETİM mantığı ise sadece
ZiraatFilo'nun test ortamına özgüdür, gerçek veri mevcutken kullanılmamalıdır.

---

## 12. Entegrasyon Rehberi

Yeni projeye entegre ederken önerilen sıra:

1. **Veri şemanızda şu alanların olduğundan emin olun** (yoksa önce bunları
   ekleyin): araç başına filoya giriş tarihi, satın alım fiyatı, finansman
   tipi + tutar kırılımı, bağlı kredi(ler) + taksit planı, sigorta poliçeleri,
   araca özel gider kayıtları, şirket geneli gider kayıtları.
2. **§3'teki 5 bileşeni** kendi backend'inizde (servis katmanı / model
   metodu / management command — mimarinize göre) ayrı ayrı hesaplayan
   fonksiyonlar yazın. Her biri bağımsız test edilebilir olmalı.
3. **§4'teki hibrit güncel günlük maliyeti** kurun — bu, dashboard'da
   gösterilecek asıl "bu araç günde kaça mal oluyor" rakamıdır.
4. **§6'daki kurtaran fiyat formülünü**, kendi gerçek doluluk/rezervasyon
   verinizle birleştirin — bu, projenin nihai iş değeridir: "piyasa fiyatı X,
   benim kurtaran fiyatım Y, aradaki fark sizin pazarlık payınız/riskiniz."
5. Enuygun'dan çekilen piyasa fiyatlarını, hem §9'daki fiyat tahmin
   algoritmasında (eksik veri doldurma) hem de §6'daki kurtaran fiyatla
   yan yana kıyaslamada kullanabilirsiniz.
6. §7 (gelir simülasyonu) ve §8 (satış/takas senaryoları) ihtiyaç
   duyulmadıkça atlanabilir — gerçek rezervasyon/satış verisi zaten
   varsa bunların simüle edilmiş hallerine gerek yoktur.
7. Doğrulama: her yeni bileşeni uyguladıktan sonra, §10'daki doğrulama
   adımını (dağıtılan toplam = kaynak toplam) mutlaka çalıştırın.

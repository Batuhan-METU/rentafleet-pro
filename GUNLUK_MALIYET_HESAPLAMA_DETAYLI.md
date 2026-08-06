# Günlük Maliyet Hesaplama Metodolojisi — Tam Detay

> Bu doküman, bir aracın **"şu an günde/ayda kaça mal olduğu"** (Günlük
> Maliyet) rakamının **tam olarak, bileşen bileşen, hangi veriden hangi
> formülle** hesaplandığını anlatır. Beş alt bileşenin (Kredi, Nakit,
> Muhasebe/Genel Gider, Sigorta, Operasyon) her biri; kullandığı veri kaynağı,
> dağıtım mekanizması (varsa) ve nihai günlük orana nasıl indirgendiği ile
> birlikte, Excel/script seviyesinde adım adım açıklanır.
>
> **Neden bu rakam bu kadar önemli:** Filo müdürü için piyasa kira fiyatıyla
> kıyaslanacak asıl "kurtaran fiyat" tabanı budur — "bu aracı bugün elimde
> tutmanın bana günde/ayda gerçek maliyeti nedir" sorusunun cevabı.

---

## İçindekiler

1. [Günlük Maliyet Nedir, Neden Hibrit Hesaplanır](#1-günlük-maliyet-nedir-neden-hibrit-hesaplanır)
2. [Genel Formül — Beş Bileşenin Toplamı](#2-genel-formül--beş-bileşenin-toplamı)
3. [Bileşen 1: Kredi — Günlük Maliyet ve Dağıtım Mekanizması](#3-bileşen-1-kredi--günlük-maliyet-ve-dağıtım-mekanizması)
4. [Bileşen 2: Nakit — Günlük Maliyet](#4-bileşen-2-nakit--günlük-maliyet)
5. [Bileşen 3: Muhasebe / Genel Gider — Günlük Dağıtım Mekanizması (TAM DETAY)](#5-bileşen-3-muhasebe--genel-gider--günlük-dağıtım-mekanizması-tam-detay)
6. [Bileşen 4: Sigorta/Kasko — Günlük Maliyet](#6-bileşen-4-sigortakasko--günlük-maliyet)
7. [Bileşen 5: Operasyon — Günlük Maliyet](#7-bileşen-5-operasyon--günlük-maliyet)
8. [Hepsini Birleştirme — Uçtan Uca Sayısal Örnek](#8-hepsini-birleştirme--uçtan-uca-sayısal-örnek)
9. ["Toplam (Bugüne Kadar)" ile "Günlük (Anlık Hız)" Farkı](#9-toplam-bugüne-kadar-ile-günlük-anlık-hız-farkı)
10. [Uygulama Sırası — Dile Bağımsız Pseudocode](#10-uygulama-sırası--dile-bağımsız-pseudocode)
11. [Sık Yapılan Hatalar](#11-sık-yapılan-hatalar)

---

## 1. Günlük Maliyet Nedir, Neden Hibrit Hesaplanır

"Günlük Maliyet", basitçe "bugüne kadarki toplam gider / filoda geçen gün
sayısı" gibi düz bir ortalama **DEĞİLDİR**. Böyle düz bir ortalama, azalan
bakiyeli bir kredi gibi zamanla değişen kalemlerde **YANLIŞ** sonuç verir —
çünkü bir kredinin faiz kısmı zamanla küçülür, dolayısıyla "geçmiş ortalaması"
ile "şu anki gerçek oran" birbirinden farklıdır.

Bu yüzden her bileşen için, o bileşenin doğasına en uygun yöntem
kullanılır — bazıları **MARJİNAL/GÜNCEL** (şu an neyse o), bazıları
**ORTALAMA** (bugüne kadarki toplam / geçen gün):

| Bileşen | Yöntem | Neden |
|---|---|---|
| Kredi | **MARJİNAL** — bugünden sonraki ilk taksitin günlük tutarı | Taksitler azalan bakiyeli, zamanla küçülür — "şu an" ile "geçmiş ortalaması" farklı |
| Nakit | **SABİT** — zaten hiç değişmeyen bir oran | Formülü zaten sabit bir orana (tutar × yıllık oran/365) dayanıyor |
| Muhasebe/Genel Gider | **ORTALAMA** — bugüne kadarki toplam pay / filoda geçen gün | Bu kalemin "sıradaki taksiti" gibi bir kavramı yok, düzensiz/kümülatif bir paydır |
| Sigorta | **MARJİNAL/GÜNCEL** — bugün aktif olan poliçenin günlük maliyeti | Poliçe zaten sabit yıllık tutarlı, "şu an" oranı direkt bellidir |
| Operasyon | **ORTALAMA** — bugüne kadarki toplam / filoda geçen gün | Düzensiz aralıklarla gerçekleşir (bazı ay bakım var, bazı ay yok), "sıradaki işlem" tahmin edilemez |

---

## 2. Genel Formül — Beş Bileşenin Toplamı

```
Günlük Maliyet =  Kredi_Günlük(marjinal)
                + Nakit_Günlük(sabit)
                + Muhasebe_Günlük(ortalama)
                + Sigorta_Günlük(marjinal)
                + Operasyon_Günlük(ortalama)
```

Her bileşen **BAĞIMSIZ** hesaplanır ve en sonda toplanır — aralarında
çapraz bağımlılık yoktur. Şimdi her birini tek tek, veri kaynağından
başlayarak inceleyelim.

---

## 3. Bileşen 1: Kredi — Günlük Maliyet ve Dağıtım Mekanizması

### 3.1 Veri Kaynağı

Bir kredinin taksit planı (her taksit için: taksit tarihi, taksit tutarı,
anapara, faiz, vergi kırılımı — bkz. amortisman formülü aşağıda) ve o
krediye bağlı araçların listesi.

### 3.2 Taksit Planı (Amortisman) — Kredinin Kendi İçinde

```
P = Kredi Tutarı, r = Aylık Faiz Oranı, n = Vade (ay)

Sabit Taksit Tutarı = P × r / (1 − (1+r)^−n)

Her ay:
  Faiz(ay)     = Kalan Anapara × r
  Vergi(ay)    = Faiz(ay) × vergi_oranı        (Türkiye'de BSMV ~%5)
  Anapara(ay)  = Sabit Taksit Tutarı − Faiz(ay) − Vergi(ay)
  Kalan Anapara -= Anapara(ay)
```

Bu adımın çıktısı: krediye ait, her ay için bir satır (Taksit Tarihi, Taksit
Tutarı) listesi. Henüz hiçbir araca bölüştürülmedi.

### 3.3 Krediyi Araçlara Ağırlıklı Dağıtma

Bir kredi birden fazla aracı finanse edebileceği için, her taksit tutarı
krediye bağlı TÜM araçlara **fiyat/tutar × gün ağırlıklı** dağıtılır:

```
Dönem: bir önceki taksit tarihinden (dahil değil) bu taksitin tarihine (dahil) kadar
       (ilk taksit için: kredinin başlangıç tarihinden itibaren)

ağırlık(araç, dönem) = araç_kredi_ile_finanse_edilen_tutar × dönem_içindeki_gün_sayısı
   (aracın TAM FİYATI değil, SADECE kredi payı — karma finansmanlı araçlarda önemli)

gün_sayısı = (dönem_bitiş − max(dönem_başlangıç, aracın_filoya_giriş_tarihi)).gün   [+1 YOK]

pay(araç, dönem) = ağırlık(araç, dönem) / Σ(dönemdeki TÜM araçların ağırlığı) × dönemin_taksit_tutarı

günlük(araç, dönem) = pay(araç, dönem) / 30   ← basitleştirme: gerçek gün sayısı değil sabit 30
```

**Doğrulama:** Bir kredinin TÜM dönemlerde dağıttığı toplam pay = kredinin
taksit tutarları toplamına (yuvarlama farkı hariç) eşit olmalı.

### 3.4 Dashboard İçin Güncel/Marjinal Günlük Kredi Oranı

```
Kredi_Günlük(araç) = Σ (aracın bağlı olduğu HER kredi için:
                        bugünden sonraki İLK taksitin, §3.3'te hesaplanmış günlük tutarı)
```

Bulma yöntemi: aracın bağlı olduğu taksitleri (kredi no, taksit tarihi)'ne
göre sıralayın, taksit_tarihi ≥ bugün olan İLK satırı her kredi için ayrı ayrı
alın, günlük tutarlarını toplayın. **Araç birden fazla krediye bağlıysa
HER kredi ayrı ayrı hesaba katılmalı — birini atlamak eksik hesaba yol açar.**

**Performans notu:** Araç başına ayrı sorgu atmak yerine, tüm gelecek
taksitleri (kredi no + taksit tarihine göre sıralı) tek seferde çekip, her
kredi için görülen ilk satırı tutan bir set/map ile ilerlemek N+1 sorgu
problemini önler.

---

## 4. Bileşen 2: Nakit — Günlük Maliyet

### 4.1 Veri Kaynağı

Aracın "Nakit ile Finanse Edilen Tutar" alanı (tek bir sayı, dağıtıma/havuza
gerek yok — bkz. önceki dokümanda §4.1'deki gerekçe: nakit paylaşılan bir
kaynak değildir, doğrudan araca aittir).

### 4.2 Formül

```
Nakit_Günlük(araç) = Nakit ile Finanse Edilen Tutar × (Yıllık Mevduat Faiz Oranı / 365)
```

Bu oran **SABİTTİR**, zamanla değişmez — "marjinal" ile "ortalama" arasında
kredi'deki gibi bir fark yoktur, ikisi zaten aynı sayıdır. Bu projede yıllık
oran %45 sabit varsayılmıştır (gerçek/güncel piyasa mevduat oranıyla
değiştirilmeli).

---

## 5. Bileşen 3: Muhasebe / Genel Gider — Günlük Dağıtım Mekanizması (TAM DETAY)

Bu bileşen, şirketin araca özel OLMAYAN genel giderlerinin (personel
maaşları, kira, elektrik, danışmanlık, sigorta primi dışındaki idari giderler
vb.) filodaki araçlara **GÜNLÜK bazda, fiyat ağırlıklı** dağıtılmasıdır.
Aşağıda, gerçek projede bunun Excel/script seviyesinde ADIM ADIM nasıl
yapıldığı anlatılıyor.

### 5.1 Girdi Verisi

Şirketin muhasebe kayıtları (genel muhasebe defteri / masraf merkezi
raporu) — her satırda:

- **Masraf Merkezi Kodu**: giderin hangi merkeze (araç şasi kodu VEYA genel/
  idari bir kod, örn. "GENEL") ait olduğu
- **Tarih**: giderin gerçekleştiği gün
- **Borç / Alacak** (ya da doğrudan tutar): o kaydın parasal değeri

### 5.2 Adım 1 — Araca Özel Olmayan Satırları Ayıklama

```
Muhasebe_Genel_Giderleri = TÜM_muhasebe_kayıtları.filtrele(
    Masraf_Merkezi_Kodu ∉ {filodaki_tüm_araçların_şasi_kodları}
)
```

Yani: Masraf Merkezi Kodu, gerçek bir araç şasi koduysa (araca özel bir gider
ise — bakım, lastik vb.) bu havuza HİÇ girmez, o zaten §7'deki Operasyon
bileşenine gider. Sadece "hangi araca ait olduğu belirsiz/genel" kayıtlar bu
havuzda toplanır.

### 5.3 Adım 2 — Net Tutar ve Günlük Toplam

```
Net_Tutar(satır) = Borç(satır) − Alacak(satır)

Günlük_Toplam_Gider[gün] = Σ Net_Tutar(satır)  için o satırın Tarih'i = gün olan TÜM satırlar
```

**Şube ayrımı YOK** — tüm şubelerin/lokasyonların o güne ait genel gideri
TEK bir havuzda toplanır (örn. 5 farklı şubenin o günkü toplam kira+personel
gideri hepsi birlikte, tek bir "o günün toplam genel gideri" sayısına
indirgenir).

### 5.4 Adım 3 — Her Gün İçin Fiyat Ağırlıklı Dağıtım

Bu, en kritik adımdır. **Her gün için AYRI AYRI**, o gün itibarıyla filoda
bulunan (yani o güne kadar filoya girmiş olan) TÜM araçlara, aracın satın
alım fiyatıyla orantılı olarak o günün toplam genel gideri dağıtılır:

```
her gün için:
    filodaki_araçlar[gün] = {araç : araç.filoya_giriş_tarihi ≤ gün}   ← o gün itibarıyla filoda olan TÜM araçlar
    toplam_fiyat[gün]     = Σ (fiyat(araç))  filodaki_araçlar[gün] içindeki her araç için

    her araç ∈ filodaki_araçlar[gün] için:
        pay(araç, gün) = fiyat(araç) / toplam_fiyat[gün] × Günlük_Toplam_Gider[gün]
```

> **Önemli benzerlik notu:** Bu formül, aslında §3.3'teki kredi dağıtım
> formülünün **"dönem = 1 gün" özel halidir.** Kredi dağıtımında ağırlık =
> `tutar × dönem_gün_sayısı` idi; burada dönem her zaman tam 1 gün olduğu
> için ağırlık basitçe `fiyat × 1 = fiyat`e indirgenir. Yani aynı "fiyat/
> tutar ağırlıklı orantısal dağıtım" prensibi, sadece dönem uzunluğu farklı
> (kredide aylık dönem, burada günlük dönem) olarak tekrar kullanılıyor.

**Eğer o gün filoda hiç araç yoksa** (`toplam_fiyat[gün] = 0`), o günün
gideri dağıtılamaz — bu durumu atlayın (sıfıra bölme hatası vermeyin) ve
isterseniz "dağıtılamayan tutar" olarak ayrıca raporlayın.

### 5.5 Adım 4 — Araç Bazında Toplama

```
Aracın Muhasebe Gider Payı (Dönem Toplamı) = Σ pay(araç, gün)   TÜM günler için (kapsanan tüm dönem boyunca)
```

Bu, kapsanan tüm dönem (örn. "Ocak-Haziran 2026" gibi kapanmış bir muhasebe
dönemi) için aracın toplam genel gider payıdır — kredi/nakit gibi "bugüne
kadar/kalan" ayrımına gerek yoktur, çünkü kaynak veri zaten kapanmış/geçmiş
bir dönemi kapsar (henüz gerçekleşmemiş gelecek genel gider tahmini
YAPILMAZ — sadece gerçekleşmiş muhasebe kayıtları dağıtılır).

**Doğrulama:** Tüm araçlara dağıtılan toplam pay, kaynaktaki toplam genel
gider tutarına (tüm günlerin toplamı) eşit olmalı (yuvarlama farkı hariç).

### 5.6 Bu Toplamı GÜNLÜK Orana Çevirme (Hibrit Formül İçin)

§2'deki genel günlük maliyet formülünde kullanılacak "Muhasebe_Günlük" değeri,
§5.5'teki TOPLAM payın **basit ortalamasıdır** — çünkü bu kalemin "sıradaki
taksiti" gibi bir kavramı yoktur:

```
Muhasebe_Günlük(araç) = Aracın Muhasebe Gider Payı (Dönem Toplamı) / (bugün − aracın_filoya_giriş_tarihi).gün
```

**Dikkat:** Bölen, "muhasebe döneminin kapsadığı gün sayısı" DEĞİL, aracın
**filoya giriş tarihinden bugüne kadar geçen TOPLAM gün sayısıdır** — bu,
projenin kendi içindeki bir basitleştirmedir (gerçek muhasebe dönemi 6 ay
gibi kapanmış bir pencereyle sınırlıyken, günlük orana çevirirken aracın TÜM
filodaki ömrüne yayılıyor). Kendi projenizde daha hassas bir yaklaşım
isterseniz, bölen olarak "muhasebe döneminin gün sayısı" (örn. 181 gün) ile
"aracın o dönem içinde filoda olduğu gün sayısı"nın minimumunu kullanabilir,
ama mevcut sistemde basitlik tercih edilmiştir.

### 5.7 Bu Kalem Hangi Üst Kategoriye Girer

Bu projede Muhasebe Gider Payı, ayrı bir kategori olarak DEĞİL, **Finansman
Giderleri** altına eklenmiştir (kullanıcı/iş kararı):

```
Toplam Finansman Maliyeti (Bugüne Kadar) = Kredi Faizi (Bugüne Kadar)
                                          + Nakit Fırsat Maliyeti (Bugüne Kadar)
                                          + Muhasebe Gider Payı (Dönem Toplamı)
```

Kendi projenizde bunu ayrı bir "Genel Gider" kategorisi olarak da
sunabilirsiniz — bu sadece raporlama/gruplama tercihidir, matematiği
değiştirmez.

---

## 6. Bileşen 4: Sigorta/Kasko — Günlük Maliyet

### 6.1 Veri Kaynağı

Aracın poliçeleri (tip, tutar, başlangıç/bitiş tarihi) — havuzlama/dağıtım
YOK, her poliçe zaten tek bir araca ait.

### 6.2 Formül

```
Poliçe_Günlük_Maliyet = Poliçe Tutarı / 365
```

Birden fazla poliçe tipi varsa (Trafik + Kasko + Yeşil Kart), bugün itibarıyla
AKTİF olan (başlangıç ≤ bugün ≤ bitiş) poliçelerin günlük maliyetleri
toplanır:

```
Sigorta_Günlük(araç) = Σ Poliçe_Günlük_Maliyet(p)   bugün itibarıyla aktif olan her poliçe p için
```

**Süresi dolmuş ama sistemde yeni kaydı henüz girilmemiş poliçe:** en son
biten poliçe(ler) aynı günlük oranla **YENİLENMİŞ** varsayılır — sigorta
maliyeti aniden sıfıra düşürülmez (araç fiilen sigortasız kalmıyor, sadece
kayıt gecikmiş oluyor).

---

## 7. Bileşen 5: Operasyon — Günlük Maliyet

### 7.1 Veri Kaynağı

Araca özel, doğrudan tarihli işlem kayıtları (bakım, lastik, hasar, yakıt,
muayene vb.) — dağıtım YOK, zaten araç+tarih bazlı kayıtlı.

### 7.2 Toplam ve Ortalamaya Çevirme

```
Aracın Toplam Operasyon Gideri = Σ (o araca ait TÜM işlem kayıtlarının net tutarı)

Operasyon_Günlük(araç) = Aracın Toplam Operasyon Gideri / (bugün − aracın_filoya_giriş_tarihi).gün
```

Bu kalemde "sıradaki bakımın ne zaman/ne tutarda olacağı" bilinemeyeceği
için MARJİNAL bir oran kavramı yoktur — düz ortalama kullanılır. Aynı
mantık, §5.6'daki Muhasebe bileşeni için de geçerlidir.

---

## 8. Hepsini Birleştirme — Uçtan Uca Sayısal Örnek

**Senaryo:** Karma finansmanlı bir araç, 400 gündür filoda.

| Bileşen | Veri | Hesap | Günlük Sonuç |
|---|---|---|---|
| **Kredi** (kredi payı: 480.000 TL, bir sonraki taksitin payı) | O krediye bağlı havuzda bu araca düşen bir sonraki ayın payı: 28.500 TL | 28.500 / 30 | **950,00 TL/gün** |
| **Nakit** (nakit payı: 320.000 TL, yıllık %45) | 320.000 × 0,45 / 365 | — | **394,52 TL/gün** |
| **Muhasebe** (dönem toplam payı: 45.000 TL, 400 gün filoda) | 45.000 / 400 | — | **112,50 TL/gün** |
| **Sigorta** (Trafik 8.000 TL/yıl + Kasko 32.000 TL/yıl, ikisi de aktif) | (8.000+32.000)/365 | — | **109,59 TL/gün** |
| **Operasyon** (toplam gerçekleşen gider: 18.000 TL, 400 gün filoda) | 18.000 / 400 | — | **45,00 TL/gün** |

```
Günlük Maliyet = 950,00 + 394,52 + 112,50 + 109,59 + 45,00 = 1.611,61 TL/gün
```

Bu rakam × 30 ≈ **48.348 TL/ay** — bu aracı elde tutmanın güncel aylık
gerçek maliyetidir. Piyasa kira fiyatıyla (enuygun vb.) kıyaslanacak taban
tam olarak budur.

---

## 9. "Toplam (Bugüne Kadar)" ile "Günlük (Anlık Hız)" Farkı

Bu iki kavramı karıştırmamak kritiktir — ikisi de gerçek, ikisi de doğru,
ama FARKLI sorulara cevap verir:

| Kavram | Soru | Nasıl Hesaplanır |
|---|---|---|
| **Toplam / Bugüne Kadar** | "Bu araç bugüne kadar TOPLAM ne kadara mal oldu?" | Her bileşenin kendi kümülatif "bugüne kadar tahakkuk eden" tutarlarının toplamı (kredi: geçmiş taksitler toplamı; nakit: günlük sabit oran × geçen gün; muhasebe: dönem payı toplamı; sigorta: günlük oran × geçen gün; operasyon: tüm kayıtların toplamı) |
| **Günlük (Anlık Hız)** | "Bu araç ŞU AN günde ne kadara mal oluyor?" | §2'deki hibrit formül — bazı bileşenler marjinal/güncel (kredi, sigorta), bazıları ortalama (muhasebe, operasyon), nakit zaten sabit |

**İkisi arasındaki ilişki NEDEN doğrusal DEĞİL:** "Toplam / Geçen Gün
Sayısı" size düz bir tarihi ortalama verir, ama bu "şu anki" günlük hızla
AYNI SAYI OLMAK ZORUNDA DEĞİLDİR — özellikle kredi bileşeninde (azalan
bakiyeli olduğu için taksitin faiz kısmı zamanla küçülür, yani genelde
"marjinal/güncel" oran "tarihi ortalama"dan DAHA DÜŞÜK çıkar). Bu ikisini
aynı sayı sanıp birini diğeri yerine kullanmak, sistemde en sık rastlanan
kavramsal hatadır.

---

## 10. Uygulama Sırası — Dile Bağımsız Pseudocode

```
function gunluk_maliyet_hesapla(arac, bugun):

    # 1) KREDİ — marjinal
    kredi_gunluk = 0
    for kredi in arac.bagli_krediler:
        gelecek_taksit = kredi.taksitler
            .filter(taksit_tarihi >= bugun)
            .sort_by(taksit_tarihi)
            .first()
        if gelecek_taksit:
            kredi_gunluk += gelecek_taksit.gunluk_tutar   # bkz. §3.3 — zaten önceden dağıtılmış günlük tutar

    # 2) NAKİT — sabit
    nakit_gunluk = arac.nakit_ile_finanse_tutar * YILLIK_MEVDUAT_ORANI / 365

    # 3) MUHASEBE — ortalama
    gun_sayisi_filoda = (bugun - arac.filoya_giris_tarihi).gun
    muhasebe_gunluk = 0
    if gun_sayisi_filoda > 0 and arac.muhasebe_gider_payi_toplam:
        muhasebe_gunluk = arac.muhasebe_gider_payi_toplam / gun_sayisi_filoda

    # 4) SİGORTA — marjinal/güncel
    sigorta_gunluk = 0
    for police in arac.policeler:
        if police.baslangic <= bugun <= police.bitis:
            sigorta_gunluk += police.tutar / 365

    # 5) OPERASYON — ortalama
    operasyon_gunluk = 0
    if gun_sayisi_filoda > 0:
        operasyon_gunluk = arac.operasyon_toplam_gideri / gun_sayisi_filoda

    return kredi_gunluk + nakit_gunluk + muhasebe_gunluk + sigorta_gunluk + operasyon_gunluk
```

**Ön koşul (bu fonksiyonun doğru çalışması için önceden hazır olması
gerekenler):**
1. Her kredinin taksit planı ve krediye bağlı araçlara §3.3'teki ağırlıklı
   dağıtım uygulanmış, her taksit için araç bazında `gunluk_tutar` hazır olmalı.
2. Her aracın `muhasebe_gider_payi_toplam` alanı, §5'teki günlük fiyat-ağırlıklı
   dağıtım ile önceden (toplu/batch olarak, tüm dönem için bir kere) hesaplanıp
   araca yazılmış olmalı — bu, her `gunluk_maliyet_hesapla()` çağrısında
   yeniden hesaplanacak kadar pahalı bir işlem değildir, günlük/periyodik bir
   toplu işte (batch job) önceden hesaplanıp saklanmalıdır.
3. `arac.operasyon_toplam_gideri`, aracın tüm işlem kayıtlarının basit
   toplamı olarak önceden agregat edilmiş olmalı (ya her çağrıda SUM
   sorgusu, ya da önceden hesaplanmış bir alan — performansa göre seçilir).

---

## 11. Sık Yapılan Hatalar

1. **Muhasebe dağıtımında şube ayrımı yapılmış olabilir** (§5.3) —
   bilinçli olarak YOK, tüm şubelerin toplam günlük gideri tek havuzda
   toplanıp dağıtılmalı.
2. **Muhasebe dağıtımında "o gün filodaki araçlar" yanlış hesaplanmış
   olabilir** (§5.4) — sadece `filoya_giriş_tarihi ≤ o_gün` olan araçlar
   dahil edilmeli; henüz filoya girmemiş bir araç o günün genel giderinden
   pay ALAMAZ.
3. **Muhasebe/Operasyon günlük oranı için "marjinal/sıradaki" bir değer
   aranmış olabilir** — bu iki kalemde böyle bir kavram YOK, sadece
   ORTALAMA kullanılmalı (§5.6, §7.2).
4. **Kredi günlük oranı için "bugüne kadarki ortalama" kullanılmış olabilir**
   — kredi bileşeni MUTLAKA marjinal (gelecek ilk taksit) olmalı, aksi halde
   azalan bakiyeli kredilerde sistematik olarak YANLIŞ (genelde ŞİŞİRİLMİŞ)
   bir günlük maliyet çıkar.
5. **"Toplam/Bugüne Kadar" ile "Günlük" birbirinin yerine kullanılmış
   olabilir** (§9) — biri kümülatif toplam, diğeri anlık hız; dashboard'da
   hangisinin gösterildiğine dikkat edin, ikisi farklı sayılardır ve
   farklı UI alanlarında ayrı ayrı gösterilmelidir.
6. **Sıfıra bölme hataları** — bir araç filoya bugün girmişse
   `gun_sayisi_filoda = 0` olur; bu durumda Muhasebe/Operasyon günlük
   oranı hesaplanamaz (0/0), bu satırlar 0 olarak ele alınmalı, hata
   fırlatılmamalı.
7. **Muhasebe dağıtımında sıfır toplam fiyatlı bir gün varsa** (o gün
   filoda hiç fiyatlı araç yoksa) sıfıra bölme hatası çıkabilir — bu
   günler atlanmalı (dağıtılamayan tutar olarak ayrıca not edilebilir).
8. **Süresi dolmuş sigorta poliçesi günlük hesaptan tamamen düşürülmüş
   olabilir** (§6.2) — yenilenmiş varsayılıp aynı oranla devam ettirilmeli.

"""
Answer / precedent pairs for the reasoning-panel dataset (used by build_datasets.py).

For each scenario:
  reference   a short correct answer, in every language the scenario exists in
  relevant    corpus posts on the same issue (taken from the retrieval labels);
              the panel should give these a high usage score
  irrelevant  corpus posts on an unrelated issue, standing in for a bad
              retrieval; the panel should give these a low score and must not
              present them as support

The reference answers follow the rubrics and carry the same caveat: drafted by
an AI assistant, not yet checked by a lawyer or by native speakers.
"""


def _r(en, hi, hien, ta, kn):
    return {"en": en, "hi": hi, "hi-en": hien, "ta": ta, "kn": kn}


PARALLEL = {
    "P01": dict(relevant=[754, 2845], irrelevant=[150], reference=_r(
        "Under section 17 of the Protection of Women from Domestic Violence Act, 2005 you have a right to live in the shared household even though it belongs to your in-laws. You can apply to the Magistrate under section 12 for a residence order under section 19.",
        "घरेलू हिंसा से महिलाओं का संरक्षण अधिनियम, 2005 की धारा 17 के तहत आपको साझा घर में रहने का अधिकार है, भले ही घर आपके सास-ससुर के नाम हो। आप धारा 12 के तहत मजिस्ट्रेट के पास अर्ज़ी देकर धारा 19 के तहत निवास आदेश माँग सकती हैं।",
        "Domestic Violence Act, 2005 ke section 17 ke under aapko shared household me rehne ka right hai, chahe ghar aapke in-laws ke naam ho. Aap section 12 ke under Magistrate ke paas application dekar section 19 ka residence order maang sakti hain.",
        "குடும்ப வன்முறையிலிருந்து பெண்களைப் பாதுகாக்கும் சட்டம், 2005-இன் பிரிவு 17-இன் கீழ், வீடு உங்கள் மாமனார் மாமியார் பெயரில் இருந்தாலும், அந்தப் பகிர்ந்த வீட்டில் வசிக்க உங்களுக்கு உரிமை உண்டு. பிரிவு 12-இன் கீழ் நீதித்துறை நடுவரிடம் மனு செய்து, பிரிவு 19-இன் கீழ் குடியிருப்பு உத்தரவைப் பெறலாம்.",
        "ಕೌಟುಂಬಿಕ ಹಿಂಸೆಯಿಂದ ಮಹಿಳೆಯರ ಸಂರಕ್ಷಣಾ ಕಾಯ್ದೆ, 2005ರ ಕಲಂ 17ರ ಅಡಿಯಲ್ಲಿ, ಮನೆ ನಿಮ್ಮ ಅತ್ತೆ-ಮಾವನ ಹೆಸರಿನಲ್ಲಿದ್ದರೂ, ಆ ಹಂಚಿಕೆಯ ಮನೆಯಲ್ಲಿ ವಾಸಿಸುವ ಹಕ್ಕು ನಿಮಗಿದೆ. ಕಲಂ 12ರ ಅಡಿಯಲ್ಲಿ ಮ್ಯಾಜಿಸ್ಟ್ರೇಟ್‌ಗೆ ಅರ್ಜಿ ಸಲ್ಲಿಸಿ ಕಲಂ 19ರ ನಿವಾಸ ಆದೇಶ ಪಡೆಯಬಹುದು.")),
    "P02": dict(relevant=[69, 123], irrelevant=[1235], reference=_r(
        "As Hindus you can file a joint petition for divorce by mutual consent under section 13B of the Hindu Marriage Act once you have lived separately for a year. After the first motion there is a six-month waiting period before the second motion, which the court can waive in suitable cases.",
        "हिंदू होने के नाते आप दोनों एक साल अलग रहने के बाद हिंदू विवाह अधिनियम की धारा 13बी के तहत आपसी सहमति से तलाक की संयुक्त याचिका दे सकते हैं। पहले मोशन के बाद दूसरे मोशन से पहले छह महीने का इंतज़ार होता है, जिसे अदालत उचित मामलों में माफ़ कर सकती है।",
        "Hindu hone ke naate aap dono ek saal alag rehne ke baad Hindu Marriage Act ke section 13B ke under mutual consent divorce ki joint petition file kar sakte hain. First motion ke baad second motion se pehle 6 mahine ka waiting period hota hai, jise court suitable cases me waive kar sakti hai.",
        "நீங்கள் இந்துக்கள் என்பதால், ஓராண்டு பிரிந்து வாழ்ந்த பிறகு இந்து திருமணச் சட்டத்தின் பிரிவு 13B-இன் கீழ் பரஸ்பர சம்மத விவாகரத்துக்குக் கூட்டு மனு தாக்கல் செய்யலாம். முதல் மனுவுக்குப் பிறகு இரண்டாவது மனுவுக்கு முன் ஆறு மாத காத்திருப்புக் காலம் உண்டு; தகுந்த வழக்குகளில் நீதிமன்றம் அதைத் தளர்த்தலாம்.",
        "ನೀವು ಹಿಂದೂಗಳಾಗಿರುವುದರಿಂದ, ಒಂದು ವರ್ಷ ಬೇರೆಯಾಗಿ ವಾಸಿಸಿದ ನಂತರ ಹಿಂದೂ ವಿವಾಹ ಕಾಯ್ದೆಯ ಕಲಂ 13ಬಿ ಅಡಿಯಲ್ಲಿ ಪರಸ್ಪರ ಒಪ್ಪಿಗೆಯ ವಿಚ್ಛೇದನಕ್ಕೆ ಜಂಟಿ ಅರ್ಜಿ ಸಲ್ಲಿಸಬಹುದು. ಮೊದಲ ಮೋಷನ್ ನಂತರ ಎರಡನೇ ಮೋಷನ್‌ಗೆ ಮೊದಲು ಆರು ತಿಂಗಳ ಕಾಯುವ ಅವಧಿ ಇದೆ; ಸೂಕ್ತ ಪ್ರಕರಣಗಳಲ್ಲಿ ಕೋರ್ಟ್ ಅದನ್ನು ಮನ್ನಾ ಮಾಡಬಹುದು.")),
    "P04": dict(relevant=[1186, 974], irrelevant=[973], reference=_r(
        "You can apply to the Magistrate under section 12 of the Domestic Violence Act for protection, residence and monetary relief orders, and claim maintenance under section 125 CrPC (section 144 BNSS). You can also lodge a police complaint for cruelty under section 498A IPC (section 85 BNS).",
        "आप घरेलू हिंसा अधिनियम की धारा 12 के तहत मजिस्ट्रेट से संरक्षण, निवास और आर्थिक राहत के आदेश माँग सकती हैं, और दंड प्रक्रिया संहिता की धारा 125 (बीएनएसएस धारा 144) के तहत भरण-पोषण का दावा कर सकती हैं। क्रूरता के लिए आप आईपीसी धारा 498ए (बीएनएस धारा 85) के तहत पुलिस में शिकायत भी कर सकती हैं।",
        "Aap Domestic Violence Act ke section 12 ke under Magistrate se protection, residence aur monetary relief ke orders maang sakti hain, aur CrPC section 125 (BNSS section 144) ke under maintenance claim kar sakti hain. Cruelty ke liye aap IPC section 498A (BNS section 85) ke under police complaint bhi kar sakti hain.",
        "குடும்ப வன்முறைச் சட்டத்தின் பிரிவு 12-இன் கீழ் நீதித்துறை நடுவரிடம் பாதுகாப்பு, குடியிருப்பு மற்றும் பண நிவாரண உத்தரவுகளைக் கோரலாம்; குற்றவியல் நடைமுறைச் சட்டம் பிரிவு 125 (BNSS பிரிவு 144)-இன் கீழ் ஜீவனாம்சமும் கோரலாம். கொடுமைக்காக IPC பிரிவு 498A (BNS பிரிவு 85)-இன் கீழ் காவல் நிலையத்தில் புகாரும் அளிக்கலாம்.",
        "ಕೌಟುಂಬಿಕ ಹಿಂಸೆ ಕಾಯ್ದೆಯ ಕಲಂ 12ರ ಅಡಿಯಲ್ಲಿ ಮ್ಯಾಜಿಸ್ಟ್ರೇಟ್‌ರಿಂದ ರಕ್ಷಣೆ, ನಿವಾಸ ಮತ್ತು ಹಣಕಾಸಿನ ಪರಿಹಾರದ ಆದೇಶಗಳನ್ನು ಕೋರಬಹುದು; ಸಿಆರ್‌ಪಿಸಿ ಕಲಂ 125 (ಬಿಎನ್‌ಎಸ್‌ಎಸ್ ಕಲಂ 144) ಅಡಿಯಲ್ಲಿ ಜೀವನಾಂಶವನ್ನೂ ಕೇಳಬಹುದು. ಕ್ರೌರ್ಯಕ್ಕಾಗಿ ಐಪಿಸಿ ಕಲಂ 498ಎ (ಬಿಎನ್‌ಎಸ್ ಕಲಂ 85) ಅಡಿಯಲ್ಲಿ ಪೊಲೀಸ್ ದೂರು ಸಹ ನೀಡಬಹುದು.")),
    "P08": dict(relevant=[1103, 86], irrelevant=[381], reference=_r(
        "Yes. You can claim maintenance for yourself and your daughter under section 125 CrPC (section 144 BNSS) in the court where you now live, and ask for interim maintenance. The amount will depend on your husband's income and your needs.",
        "हाँ। आप अपने और अपनी बेटी के लिए दंड प्रक्रिया संहिता की धारा 125 (बीएनएसएस धारा 144) के तहत उस अदालत में भरण-पोषण माँग सकती हैं जहाँ आप अभी रहती हैं, और अंतरिम भरण-पोषण भी माँग सकती हैं। रकम आपके पति की आय और आपकी ज़रूरतों पर निर्भर करेगी।",
        "Haan. Aap apne aur apni beti ke liye CrPC section 125 (BNSS section 144) ke under us court me maintenance claim kar sakti hain jahan aap abhi rehti hain, aur interim maintenance bhi maang sakti hain. Amount aapke husband ki income aur aapki zaruraton par depend karega.",
        "ஆம். நீங்கள் தற்போது வசிக்கும் இடத்தின் நீதிமன்றத்தில், குற்றவியல் நடைமுறைச் சட்டம் பிரிவு 125 (BNSS பிரிவு 144)-இன் கீழ் உங்களுக்கும் உங்கள் மகளுக்கும் ஜீவனாம்சம் கோரலாம்; இடைக்கால ஜீவனாம்சமும் கேட்கலாம். தொகை உங்கள் கணவரின் வருமானத்தையும் உங்கள் தேவைகளையும் பொறுத்தது.",
        "ಹೌದು. ನೀವು ಈಗ ವಾಸಿಸುತ್ತಿರುವ ಸ್ಥಳದ ಕೋರ್ಟ್‌ನಲ್ಲಿ ಸಿಆರ್‌ಪಿಸಿ ಕಲಂ 125 (ಬಿಎನ್‌ಎಸ್‌ಎಸ್ ಕಲಂ 144) ಅಡಿಯಲ್ಲಿ ನಿಮಗೂ ನಿಮ್ಮ ಮಗಳಿಗೂ ಜೀವನಾಂಶ ಕೇಳಬಹುದು; ಮಧ್ಯಂತರ ಜೀವನಾಂಶವನ್ನೂ ಕೋರಬಹುದು. ಮೊತ್ತವು ನಿಮ್ಮ ಗಂಡನ ಆದಾಯ ಮತ್ತು ನಿಮ್ಮ ಅಗತ್ಯಗಳನ್ನು ಅವಲಂಬಿಸಿರುತ್ತದೆ.")),
    "P12": dict(relevant=[944, 163], irrelevant=[134], reference=_r(
        "Yes, you can file a contested divorce petition without her consent. Under section 13(1)(ib) of the Hindu Marriage Act, desertion for a continuous period of two years is a ground, and you will have to prove that she left without reasonable cause.",
        "हाँ, आप उसकी सहमति के बिना भी तलाक की याचिका दायर कर सकते हैं। हिंदू विवाह अधिनियम की धारा 13(1)(ib) के तहत लगातार दो साल का परित्याग तलाक का आधार है, और आपको साबित करना होगा कि वह बिना उचित कारण के घर छोड़कर गई।",
        "Haan, aap uski consent ke bina bhi contested divorce petition file kar sakte hain. Hindu Marriage Act ke section 13(1)(ib) ke under lagatar do saal ka desertion divorce ka ground hai, aur aapko prove karna hoga ki wo bina reasonable cause ke ghar chhodkar gayi.",
        "ஆம், அவருடைய சம்மதம் இல்லாமலும் நீங்கள் விவாகரத்து மனு தாக்கல் செய்யலாம். இந்து திருமணச் சட்டத்தின் பிரிவு 13(1)(ib)-இன் கீழ் தொடர்ந்து இரண்டு ஆண்டுகள் கைவிட்டுச் செல்வது விவாகரத்துக்கான காரணம்; அவர் நியாயமான காரணமின்றி வீட்டை விட்டுச் சென்றார் என்பதை நீங்கள் நிரூபிக்க வேண்டும்.",
        "ಹೌದು, ಅವರ ಒಪ್ಪಿಗೆ ಇಲ್ಲದೆಯೂ ನೀವು ವಿಚ್ಛೇದನ ಅರ್ಜಿ ಸಲ್ಲಿಸಬಹುದು. ಹಿಂದೂ ವಿವಾಹ ಕಾಯ್ದೆಯ ಕಲಂ 13(1)(ib) ಅಡಿಯಲ್ಲಿ ಸತತ ಎರಡು ವರ್ಷಗಳ ಪರಿತ್ಯಾಗ ವಿಚ್ಛೇದನಕ್ಕೆ ಆಧಾರ; ಅವರು ಸಮಂಜಸ ಕಾರಣವಿಲ್ಲದೆ ಮನೆ ಬಿಟ್ಟು ಹೋದರು ಎಂದು ನೀವು ಸಾಬೀತುಪಡಿಸಬೇಕು.")),
    "P15": dict(relevant=[165, 131], irrelevant=[490], reference=_r(
        "Under section 6(a) of the Hindu Minority and Guardianship Act the custody of a child below five is ordinarily with the mother, and the child's welfare is the deciding factor. You can file for custody under the Guardians and Wards Act and ask for an interim order stopping him from taking her away.",
        "हिंदू अल्पवयस्कता और संरक्षकता अधिनियम की धारा 6(क) के अनुसार पाँच साल से छोटे बच्चे की कस्टडी आम तौर पर माँ के पास रहती है, और फैसला बच्चे के हित को देखकर होता है। आप संरक्षक और प्रतिपाल्य अधिनियम के तहत कस्टडी की अर्ज़ी देकर अंतरिम आदेश माँग सकती हैं कि वह बच्ची को न ले जाए।",
        "Hindu Minority and Guardianship Act ke section 6(a) ke hisaab se paanch saal se chhote bacche ki custody aam taur par maa ke paas rehti hai, aur faisla bacche ke welfare ko dekhkar hota hai. Aap Guardians and Wards Act ke under custody petition file karke interim order maang sakti hain ki wo bacchi ko na le jaye.",
        "இந்து இளவர் மற்றும் காப்பாளர் சட்டத்தின் பிரிவு 6(a)-இன்படி ஐந்து வயதுக்குட்பட்ட குழந்தையின் பாதுகாப்பு பொதுவாகத் தாயிடமே இருக்கும்; குழந்தையின் நலனே முடிவைத் தீர்மானிக்கும். காப்பாளர் மற்றும் காப்பிலுள்ளோர் சட்டத்தின் கீழ் மனு தாக்கல் செய்து, அவர் குழந்தையை எடுத்துச் செல்வதைத் தடுக்கும் இடைக்கால உத்தரவைக் கோரலாம்.",
        "ಹಿಂದೂ ಅಪ್ರಾಪ್ತ ವಯಸ್ಕತೆ ಮತ್ತು ಪೋಷಕತ್ವ ಕಾಯ್ದೆಯ ಕಲಂ 6(ಎ) ಪ್ರಕಾರ ಐದು ವರ್ಷದೊಳಗಿನ ಮಗುವಿನ ಕಸ್ಟಡಿ ಸಾಮಾನ್ಯವಾಗಿ ತಾಯಿಯ ಬಳಿ ಇರುತ್ತದೆ; ಮಗುವಿನ ಹಿತವೇ ನಿರ್ಣಾಯಕ. ಗಾರ್ಡಿಯನ್ಸ್ ಅಂಡ್ ವಾರ್ಡ್ಸ್ ಕಾಯ್ದೆಯ ಅಡಿಯಲ್ಲಿ ಅರ್ಜಿ ಸಲ್ಲಿಸಿ, ಅವರು ಮಗುವನ್ನು ಕರೆದೊಯ್ಯದಂತೆ ಮಧ್ಯಂತರ ಆದೇಶ ಕೋರಬಹುದು.")),
    "P17": dict(relevant=[2470, 2563], irrelevant=[679], reference=_r(
        "You can lodge an FIR at the police station or women's cell for cruelty under section 498A IPC (section 85 BNS) and for dowry demand under the Dowry Prohibition Act; not having complained earlier does not stop you. You can also apply under section 12 of the Domestic Violence Act for protection and residence orders.",
        "आप थाने या महिला सेल में आईपीसी धारा 498ए (बीएनएस धारा 85) के तहत क्रूरता और दहेज प्रतिषेध अधिनियम के तहत दहेज माँगने की एफआईआर दर्ज करा सकती हैं; पहले शिकायत न करना इसमें रुकावट नहीं है। आप घरेलू हिंसा अधिनियम की धारा 12 के तहत संरक्षण और निवास के आदेश के लिए भी अर्ज़ी दे सकती हैं।",
        "Aap police station ya mahila cell me IPC section 498A (BNS section 85) ke under cruelty aur Dowry Prohibition Act ke under dowry demand ki FIR karwa sakti hain; pehle complaint na karna isme rukawat nahi hai. Aap Domestic Violence Act ke section 12 ke under protection aur residence orders ke liye bhi apply kar sakti hain.",
        "IPC பிரிவு 498A (BNS பிரிவு 85)-இன் கீழ் கொடுமைக்காகவும், வரதட்சணைத் தடைச் சட்டத்தின் கீழ் வரதட்சணை கேட்டதற்காகவும் காவல் நிலையத்திலோ மகளிர் காவல் நிலையத்திலோ புகார் (FIR) அளிக்கலாம்; முன்பு புகார் கொடுக்காதது இதற்குத் தடையல்ல. குடும்ப வன்முறைச் சட்டத்தின் பிரிவு 12-இன் கீழ் பாதுகாப்பு மற்றும் குடியிருப்பு உத்தரவுகளுக்கும் மனு செய்யலாம்.",
        "ಐಪಿಸಿ ಕಲಂ 498ಎ (ಬಿಎನ್‌ಎಸ್ ಕಲಂ 85) ಅಡಿಯಲ್ಲಿ ಕ್ರೌರ್ಯಕ್ಕಾಗಿ ಮತ್ತು ವರದಕ್ಷಿಣೆ ನಿಷೇಧ ಕಾಯ್ದೆಯ ಅಡಿಯಲ್ಲಿ ವರದಕ್ಷಿಣೆ ಬೇಡಿಕೆಗಾಗಿ ಪೊಲೀಸ್ ಠಾಣೆ ಅಥವಾ ಮಹಿಳಾ ಠಾಣೆಯಲ್ಲಿ ಎಫ್‌ಐಆರ್ ದಾಖಲಿಸಬಹುದು; ಹಿಂದೆ ದೂರು ಕೊಡದಿರುವುದು ಅಡ್ಡಿಯಲ್ಲ. ಕೌಟುಂಬಿಕ ಹಿಂಸೆ ಕಾಯ್ದೆಯ ಕಲಂ 12ರ ಅಡಿಯಲ್ಲಿ ರಕ್ಷಣೆ ಮತ್ತು ನಿವಾಸ ಆದೇಶಗಳಿಗೂ ಅರ್ಜಿ ಸಲ್ಲಿಸಬಹುದು.")),
    "P19": dict(relevant=[261, 225], irrelevant=[1103], reference=_r(
        "His second marriage is void under sections 5 and 11 of the Hindu Marriage Act because your marriage still subsists, and it is bigamy punishable under section 494 IPC (section 82 BNS). You, as the aggrieved wife, have to file the complaint and prove that the second marriage ceremony took place.",
        "आपकी शादी कायम रहते उसकी दूसरी शादी हिंदू विवाह अधिनियम की धारा 5 और 11 के तहत शून्य है, और यह आईपीसी धारा 494 (बीएनएस धारा 82) के तहत द्विविवाह का अपराध है। पीड़ित पत्नी के रूप में शिकायत आपको ही करनी होगी और दूसरी शादी की रस्में होना साबित करना होगा।",
        "Aapki shaadi kayam rehte uski doosri shaadi Hindu Marriage Act ke section 5 aur 11 ke under void hai, aur ye IPC section 494 (BNS section 82) ke under bigamy ka offence hai. Aggrieved wife ke roop me complaint aapko hi karni hogi aur doosri shaadi ki rasmein hona prove karna hoga.",
        "உங்கள் திருமணம் நீடிக்கும்போது அவர் செய்த இரண்டாவது திருமணம் இந்து திருமணச் சட்டத்தின் பிரிவுகள் 5 மற்றும் 11-இன் கீழ் செல்லாது; அது IPC பிரிவு 494 (BNS பிரிவு 82)-இன் கீழ் தண்டிக்கத்தக்க இருதார மணக் குற்றம். பாதிக்கப்பட்ட மனைவி என்ற முறையில் நீங்களே புகார் அளிக்க வேண்டும்; இரண்டாவது திருமணச் சடங்குகள் நடந்தன என்பதையும் நிரூபிக்க வேண்டும்.",
        "ನಿಮ್ಮ ಮದುವೆ ಇನ್ನೂ ಜಾರಿಯಲ್ಲಿರುವಾಗ ಅವರು ಮಾಡಿಕೊಂಡ ಎರಡನೇ ಮದುವೆ ಹಿಂದೂ ವಿವಾಹ ಕಾಯ್ದೆಯ ಕಲಂ 5 ಮತ್ತು 11ರ ಅಡಿಯಲ್ಲಿ ಅಸಿಂಧು; ಅದು ಐಪಿಸಿ ಕಲಂ 494 (ಬಿಎನ್‌ಎಸ್ ಕಲಂ 82) ಅಡಿಯಲ್ಲಿ ಶಿಕ್ಷಾರ್ಹ ದ್ವಿಪತ್ನಿತ್ವದ ಅಪರಾಧ. ನೊಂದ ಪತ್ನಿಯಾಗಿ ನೀವೇ ದೂರು ಸಲ್ಲಿಸಬೇಕು ಮತ್ತು ಎರಡನೇ ಮದುವೆಯ ವಿಧಿಗಳು ನಡೆದಿವೆ ಎಂದು ಸಾಬೀತುಪಡಿಸಬೇಕು.")),
    "P24": dict(relevant=[41, 445], irrelevant=[2163], reference=_r(
        "Talaq pronounced three times in one message is void under section 3 of the Muslim Women (Protection of Rights on Marriage) Act, 2019, so your marriage continues and he cannot make you leave. You can claim a subsistence allowance for yourself and your children under section 5 of that Act, and maintenance under section 125 CrPC (section 144 BNSS).",
        "एक ही संदेश में तीन बार दिया गया तलाक मुस्लिम महिला (विवाह पर अधिकारों का संरक्षण) अधिनियम, 2019 की धारा 3 के तहत शून्य है, इसलिए आपकी शादी कायम है और वह आपको घर से नहीं निकाल सकता। आप उसी अधिनियम की धारा 5 के तहत अपने और बच्चों के लिए गुज़ारा-भत्ता और दंड प्रक्रिया संहिता की धारा 125 (बीएनएसएस धारा 144) के तहत भरण-पोषण माँग सकती हैं।",
        "Ek hi message me teen baar diya gaya talaq Muslim Women (Protection of Rights on Marriage) Act, 2019 ke section 3 ke under void hai, isliye aapki shaadi kayam hai aur wo aapko ghar se nahi nikal sakta. Aap usi Act ke section 5 ke under apne aur bacchon ke liye subsistence allowance aur CrPC section 125 (BNSS section 144) ke under maintenance maang sakti hain.",
        "ஒரே செய்தியில் மூன்று முறை சொல்லப்பட்ட தலாக், முஸ்லிம் பெண்கள் (திருமண உரிமைகள் பாதுகாப்பு) சட்டம், 2019-இன் பிரிவு 3-இன் கீழ் செல்லாது; எனவே உங்கள் திருமணம் தொடர்கிறது, அவர் உங்களை வீட்டை விட்டு வெளியேற்ற முடியாது. அதே சட்டத்தின் பிரிவு 5-இன் கீழ் உங்களுக்கும் குழந்தைகளுக்கும் வாழ்வாதாரத் தொகையும், குற்றவியல் நடைமுறைச் சட்டம் பிரிவு 125 (BNSS பிரிவு 144)-இன் கீழ் ஜீவனாம்சமும் கோரலாம்.",
        "ಒಂದೇ ಸಂದೇಶದಲ್ಲಿ ಮೂರು ಬಾರಿ ಹೇಳಿದ ತಲಾಖ್ ಮುಸ್ಲಿಂ ಮಹಿಳೆಯರ (ವಿವಾಹದ ಹಕ್ಕುಗಳ ಸಂರಕ್ಷಣೆ) ಕಾಯ್ದೆ, 2019ರ ಕಲಂ 3ರ ಅಡಿಯಲ್ಲಿ ಅಸಿಂಧು; ಆದ್ದರಿಂದ ನಿಮ್ಮ ಮದುವೆ ಮುಂದುವರಿಯುತ್ತದೆ ಮತ್ತು ಅವರು ನಿಮ್ಮನ್ನು ಮನೆಯಿಂದ ಹೊರಹಾಕುವಂತಿಲ್ಲ. ಅದೇ ಕಾಯ್ದೆಯ ಕಲಂ 5ರ ಅಡಿಯಲ್ಲಿ ನಿಮಗೂ ಮಕ್ಕಳಿಗೂ ಜೀವನ ನಿರ್ವಹಣಾ ಭತ್ಯೆ ಮತ್ತು ಸಿಆರ್‌ಪಿಸಿ ಕಲಂ 125 (ಬಿಎನ್‌ಎಸ್‌ಎಸ್ ಕಲಂ 144) ಅಡಿಯಲ್ಲಿ ಜೀವನಾಂಶ ಕೇಳಬಹುದು.")),
    "P16": dict(relevant=[180, 154], irrelevant=[134], reference=_r(
        "Yes. The court can grant you interim visitation under section 12 of the Guardians and Wards Act while your main petition is pending, and a pending domestic violence case does not by itself bar a father's access. Press for an early hearing of your interim application, and if it is still delayed you can ask the High Court to direct the family court to decide it within a fixed time.",
        "हाँ। मुख्य याचिका लंबित रहते हुए भी अदालत संरक्षक और प्रतिपाल्य अधिनियम की धारा 12 के तहत आपको अंतरिम मुलाकात का अधिकार दे सकती है, और घरेलू हिंसा का केस लंबित होना अपने आप में पिता को बच्चे से मिलने से नहीं रोकता। अपनी अंतरिम अर्ज़ी पर जल्दी सुनवाई की माँग करें; फिर भी देर हो तो हाई कोर्ट से तय समय में फैसला करने का निर्देश माँग सकते हैं।",
        "Haan. Main petition pending rehte hue bhi court Guardians and Wards Act ke section 12 ke under aapko interim visitation de sakti hai, aur DV case pending hona apne aap me father ko bacche se milne se nahi rokta. Apni interim application par jaldi hearing ki request kijiye; phir bhi delay ho to High Court se time-bound decision ka direction maang sakte hain.",
        "ஆம். முதன்மை மனு நிலுவையில் இருக்கும்போதே, காப்பாளர் மற்றும் காப்பிலுள்ளோர் சட்டத்தின் பிரிவு 12-இன் கீழ் நீதிமன்றம் உங்களுக்கு இடைக்காலமாகக் குழந்தையைச் சந்திக்கும் உரிமையை வழங்கலாம்; குடும்ப வன்முறை வழக்கு நிலுவையில் இருப்பது மட்டுமே தந்தை குழந்தையைப் பார்ப்பதைத் தடுக்காது. உங்கள் இடைக்கால மனுவை விரைவாக விசாரிக்கக் கோருங்கள்; மேலும் தாமதமானால், குறிப்பிட்ட காலத்துக்குள் முடிவு செய்ய உத்தரவிடுமாறு உயர் நீதிமன்றத்தை நாடலாம்.",
        "ಹೌದು. ಮುಖ್ಯ ಅರ್ಜಿ ಬಾಕಿ ಇರುವಾಗಲೂ ಗಾರ್ಡಿಯನ್ಸ್ ಅಂಡ್ ವಾರ್ಡ್ಸ್ ಕಾಯ್ದೆಯ ಕಲಂ 12ರ ಅಡಿಯಲ್ಲಿ ಕೋರ್ಟ್ ನಿಮಗೆ ಮಧ್ಯಂತರ ಭೇಟಿಯ ಹಕ್ಕು ನೀಡಬಹುದು; ಕೌಟುಂಬಿಕ ಹಿಂಸೆ ಕೇಸ್ ಬಾಕಿ ಇದೆ ಎಂಬ ಕಾರಣಕ್ಕೆ ಮಾತ್ರ ತಂದೆ ಮಗುವನ್ನು ಭೇಟಿಯಾಗುವುದನ್ನು ತಡೆಯಲಾಗುವುದಿಲ್ಲ. ನಿಮ್ಮ ಮಧ್ಯಂತರ ಅರ್ಜಿಯ ಶೀಘ್ರ ವಿಚಾರಣೆಗೆ ಒತ್ತಾಯಿಸಿ; ಇನ್ನೂ ವಿಳಂಬವಾದರೆ ನಿಗದಿತ ಅವಧಿಯೊಳಗೆ ತೀರ್ಮಾನಿಸಲು ನಿರ್ದೇಶಿಸುವಂತೆ ಹೈಕೋರ್ಟ್‌ಗೆ ಮನವಿ ಮಾಡಬಹುದು.")),
}

SPECIFIC = {
    "L-en-01": dict(relevant=[235, 324], irrelevant=[71, 679], reference=
        "There is no fixed formula for one-time alimony; under section 25 of the Hindu Marriage Act the court looks at both incomes, the length of the marriage and each side's needs. In a mutual consent divorce the amount is settled by agreement, so you can negotiate it down, but the court will not reduce it for you."),
    "L-en-03": dict(relevant=[388, 1479], irrelevant=[2163], reference=
        "Under section 13B(2) of the Hindu Marriage Act either spouse can withdraw consent before the second motion, so the court cannot grant a mutual consent divorce without her. You can apply for a refund of what you paid and file a contested divorce petition."),
    "L-en-04": dict(relevant=[480, 1830], irrelevant=[381], reference=
        "You cannot stop paying on your own because the maintenance is part of a court decree. You can apply under section 25(2) of the Hindu Marriage Act to have it reduced on the ground of changed circumstances, including that she is now earning."),
    "L-hi-01": dict(relevant=[1902, 1264], irrelevant=[150, 134], reference=
        "आप घरेलू हिंसा अधिनियम की धारा 12 के तहत मजिस्ट्रेट से संरक्षण, निवास और खर्चे के आदेश माँग सकती हैं, और अपने तथा दोनों बच्चों के लिए दंड प्रक्रिया संहिता की धारा 125 (बीएनएसएस धारा 144) के तहत भरण-पोषण का दावा कर सकती हैं। मारपीट के लिए आईपीसी धारा 498ए (बीएनएस धारा 85) के तहत एफआईआर भी दर्ज कराई जा सकती है।"),
    "L-hi-03": dict(relevant=[1309, 1931], irrelevant=[973], reference=
        "आप हिंदू विवाह अधिनियम की धारा 9 के तहत फैमिली कोर्ट में दांपत्य अधिकारों की बहाली की याचिका दायर कर सकते हैं। अदालत पत्नी को ज़बरदस्ती वापस नहीं भेज सकती, लेकिन डिक्री के एक साल बाद भी वह न लौटे तो यह तलाक का आधार बन जाता है; साथ में मध्यस्थता भी आज़माएँ।"),
    "L-hi-08": dict(relevant=[1103, 798], irrelevant=[679], reference=
        "हाँ। बच्चे का भरण-पोषण पाने का अधिकार तलाक से अलग है, और आप बेटे के लिए दंड प्रक्रिया संहिता की धारा 125 (बीएनएसएस धारा 144) या हिंदू विवाह अधिनियम की धारा 26 के तहत अर्ज़ी दे सकती हैं। ज़ुबानी समझौता डिक्री में दर्ज नहीं है, इसलिए उसे सीधे लागू नहीं कराया जा सकता; नई अर्ज़ी देनी होगी।"),
    "L-hien-01": dict(relevant=[2771, 1981], irrelevant=[1103, 679], reference=
        "Aap Sessions Court ya High Court me BNSS section 482 (CrPC section 438) ke under anticipatory bail ke liye apply kar sakte hain. Arnesh Kumar judgment ke hisaab se 498A me police seedha arrest nahi kar sakti, pehle notice deti hai; aur alag sheher me rehne wali behen ke against vague allegations wala case High Court quash kar sakti hai."),
    "L-hien-03": dict(relevant=[534, 2599], irrelevant=[381], reference=
        "Haan, aap Lucknow me hi CrPC section 125 (BNSS section 144) ke under maintenance ka case file kar sakti hain, chahe husband Dubai me ho. Summons embassy ke through bheja jata hai, aur wo na aaye to court ex parte order de sakti hai jo India me uski property se recover kiya ja sakta hai."),
    "L-hien-04": dict(relevant=[663, 180], irrelevant=[134], reference=
        "Aap usi family court me visitation order ko enforce karwane ke liye execution application file kar sakte hain. Court order ko jaan-boojhkar na maanna contempt of court hai, aur lagatar mana karne par court custody ke terms badal bhi sakti hai; har missed visit ka record rakhiye."),
    "L-ta-01": dict(relevant=[1902, 906], irrelevant=[490, 973], reference=
        "குடும்ப வன்முறைச் சட்டத்தின் பிரிவு 12-இன் கீழ் நீதித்துறை நடுவரிடம் மனு செய்யலாம். பிரிவு 18-இன் கீழ் பாதுகாப்பு உத்தரவும், பிரிவு 19(1)(b)-இன் கீழ் கணவரை வீட்டிலிருந்து வெளியேறச் சொல்லும் குடியிருப்பு உத்தரவும் பெறலாம்; வீடு அவர் பெயரில் இருந்தாலும் இது பொருந்தும்."),
    "L-ta-03": dict(relevant=[1321, 1552], irrelevant=[71], reference=
        "மேலும் வரதட்சணை கேட்பது வரதட்சணைத் தடைச் சட்டத்தின் கீழ் குற்றம்; துன்புறுத்தலுக்கு IPC பிரிவு 498A (BNS பிரிவு 85)-இன் கீழ் மகளிர் காவல் நிலையத்தில் புகார் அளிக்கலாம். உங்கள் நகைகள் உங்கள் சீதனம்; அவற்றைத் திருப்பித் தர மறுத்தால் நம்பிக்கை மோசடி (IPC பிரிவு 406) குற்றமாகும், குடும்ப வன்முறைச் சட்டத்தின் கீழும் திரும்பப் பெற உத்தரவு கோரலாம்."),
    "L-ta-02": dict(relevant=[1996, 1040], irrelevant=[2163], reference=
        "விவாகரத்து வழக்கு இல்லாவிட்டாலும், காப்பாளர் மற்றும் காப்பிலுள்ளோர் சட்டத்தின் கீழ் குழந்தை வசிக்கும் இடத்தின் நீதிமன்றத்தில் குழந்தையைச் சந்திக்கும் உரிமை கோரி மனு தாக்கல் செய்யலாம்; இடைக்கால அனுமதிக்கும் விண்ணப்பிக்கலாம். மூன்று வயதுக் குழந்தையின் பாதுகாப்பு பொதுவாகத் தாயிடம் இருக்கும்; ஆனால் தந்தைக்குக் குழந்தையைப் பார்க்கும் உரிமை உண்டு."),
    "L-kn-01": dict(relevant=[2873, 2184], irrelevant=[261, 150], reference=
        "ಜೀವನಾಂಶಕ್ಕೆ ನಿಗದಿತ ಸೂತ್ರವಿಲ್ಲ; ಕೋರ್ಟ್ ನಿಮ್ಮ ಆದಾಯ, ಹೊಣೆಗಾರಿಕೆಗಳು ಮತ್ತು ಹೆಂಡತಿಯ ಅಗತ್ಯ ಹಾಗೂ ಸಂಪಾದನಾ ಸಾಮರ್ಥ್ಯವನ್ನು ನೋಡುತ್ತದೆ. ಸಾಮಾನ್ಯವಾಗಿ ನಿವ್ವಳ ಆದಾಯದ ಸುಮಾರು ಕಾಲು ಭಾಗವನ್ನು ಮಾರ್ಗಸೂಚಿಯಾಗಿ ಪರಿಗಣಿಸಲಾಗುತ್ತದೆ, ಆದ್ದರಿಂದ 40,000 ಸಂಬಳಕ್ಕೆ 25,000 ಬೇಡಿಕೆ ಹೆಚ್ಚು."),
    "L-kn-03": dict(relevant=[1530, 141], irrelevant=[134], reference=
        "ದೂರಿನಲ್ಲಿ ನೀವು ಯಾರ ಹೆಸರು ಮತ್ತು ಕೃತ್ಯಗಳನ್ನು ಹೇಳುತ್ತೀರೋ ಅವರ ಮೇಲೆ ಕೇಸ್ ಆಗುತ್ತದೆ; ಗಂಡ ತಾನಾಗಿಯೇ ಆರೋಪಿಯಾಗುವುದಿಲ್ಲ. ಐಪಿಸಿ ಕಲಂ 498ಎ (ಬಿಎನ್‌ಎಸ್ ಕಲಂ 85) ಮತ್ತು ವರದಕ್ಷಿಣೆ ನಿಷೇಧ ಕಾಯ್ದೆಯ ಅಡಿಯಲ್ಲಿ ದೂರು ಕೊಡಬಹುದು, ಅಥವಾ ಕೌಟುಂಬಿಕ ಹಿಂಸೆ ಕಾಯ್ದೆಯ ಅಡಿಯಲ್ಲಿ ಅತ್ತೆ ಮತ್ತು ನಾದಿನಿಯ ವಿರುದ್ಧ ರಕ್ಷಣಾ ಆದೇಶ ಕೋರಬಹುದು."),
    "L-kn-04": dict(relevant=[2423, 491], irrelevant=[1235], reference=
        "ಮಗುವಿನ ಕಸ್ಟಡಿಯನ್ನು ಯಾರು ಹೆಚ್ಚು ಸಂಪಾದಿಸುತ್ತಾರೆ ಎಂಬುದರ ಮೇಲೆ ಅಲ್ಲ, ಮಗುವಿನ ಹಿತದ ಆಧಾರದ ಮೇಲೆ ನಿರ್ಧರಿಸಲಾಗುತ್ತದೆ. ತಂದೆಯ ಆದಾಯ ಹೆಚ್ಚಿದ್ದರೆ ಕೋರ್ಟ್ ಅವರಿಗೆ ಮಗುವಿನ ಖರ್ಚು ಕೊಡಲು ಆದೇಶಿಸುತ್ತದೆ; ನೀವು ಹಿಂದೂ ವಿವಾಹ ಕಾಯ್ದೆಯ ಕಲಂ 26ರ ಅಡಿಯಲ್ಲಿ ಮಧ್ಯಂತರ ಕಸ್ಟಡಿ ಆದೇಶ ಕೋರಬಹುದು."),
}

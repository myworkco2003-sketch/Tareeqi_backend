import re
import unicodedata

# علامات التشكيل والتطويل في اليونيكود
ARABIC_DIACRITICS = re.compile(r'[\u064B-\u065F\u0670\u0640]')

# البوادئ المكانية والإدارية الشائعة
SPATIAL_PREFIXES = re.compile(
    r'^(?:شارع|طريق|جاده|جادة|حي|بلديه|بلدية|دائره خدمات|دائرة خدمات|دائره|دائرة|منطقه|منطقة|سرفيس|سيرفيس|خط|حاره|حارة|سوق|مستشفي|مستشفى|مشفي|مشفى|جامع|مسجد|حديقه|حديقة|مركز)\s+',
    re.IGNORECASE
)

# أسماء مركبة شهيرة في طوبوغرافيا دمشق وريفها
COMPOUND_PREFIXES = ['ابو', 'كفر', 'باب', 'دير', 'تل', 'عين', 'نهر', 'خان']


def normalize_arabic(text: str) -> str:
    """
    توحيد ومعايرة النص العربي للفهرسة والبحث المطابق:
    1. إزالة حركات التشكيل والتطويل (الكشيدة).
    2. توحيد كافة أشكال الألف والهمزات (أ، إ، آ، ٱ) -> ا.
    3. توحيد التاء المربوطة والهاء في أواخر الكلمات (ة) -> ه.
    4. توحيد الألف المقصورة والياء (ى) -> ي.
    5. تنظيف الفراغات المتعددة.
    """
    if not text:
        return ""
    text = unicodedata.normalize('NFKC', str(text))
    text = ARABIC_DIACRITICS.sub('', text)
    text = re.sub(r'[أإآٱ]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()


def build_search_index_text(*parts) -> str:
    """
    بناء نص الفهرسة والبحث الموحد مع التوسيع التلقائي للكلمات المركبة وأداة التعريف:
    يضمن احتواء الفهرس على النص بشكله المنفصل والملتصق وبأداة التعريف وبدونها.
    """
    combined = " ".join(str(p) for p in parts if p)
    norm = normalize_arabic(combined)
    if not norm:
        return ""

    tokens = norm.split()
    extras = []

    # 1. توسيع الكلمات المركبة في الفهرس
    for cp in COMPOUND_PREFIXES:
        spaced = f"{cp} "
        if spaced in norm:
            extras.append(norm.replace(spaced, cp))
        joined_p = rf'\b{cp}(?=[ء-ي])'
        if re.search(joined_p, norm):
            extras.append(re.sub(joined_p, f"{cp} ", norm))

    # 2. إضافة الكلمات المجردة من "الـ"
    no_al_tokens = []
    for t in tokens:
        if t.startswith('ال') and len(t) > 3:
            no_al_tokens.append(t[2:])
            extras.append(t[2:])
        else:
            no_al_tokens.append(t)
    if no_al_tokens != tokens:
        extras.append(" ".join(no_al_tokens))

    # 3. دمج النص الأصلي مع كافة الإضافات التوسيعية
    all_chunks = [norm] + extras
    return " ".join(dict.fromkeys(all_chunks))[:500]


def generate_search_variants(query: str) -> list[str]:
    """
    توليد مشتقات وبدائل البحث الذكية لمعالجة الفراغات والبوادئ والتعريف:
    - البحث بدون همزات
    - البحث بالكلمات المركبة ملتصقة ومنفصلة (ابو رمانة <-> ابورمانة)
    - البحث بدون أداة التعريف (الـ)
    - البحث بدون بادئة التصنيف (حي، شارع، بلدية، مشفى...)
    """
    if not query:
        return []

    raw_norm = normalize_arabic(query)
    if not raw_norm or len(raw_norm) < 2:
        return [raw_norm] if raw_norm else []

    variants = {raw_norm}

    # 1. إزالة البوادئ الإدارية
    no_prefix = SPATIAL_PREFIXES.sub('', raw_norm).strip()
    if no_prefix and len(no_prefix) >= 2:
        variants.add(no_prefix)

    # 2. تبديل مشفى / مستشفى
    for v in list(variants):
        if 'مستشفي' in v:
            variants.add(v.replace('مستشفي', 'مشفي'))
        elif 'مشفي' in v:
            variants.add(v.replace('مشفي', 'مستشفي'))

    # 3. معالجة ساروجة / ساروجا / ساروحه
    for v in list(variants):
        if any(w in v for w in ['ساروجه', 'ساروجا', 'ساروحه']):
            variants.add('ساروجه')
            variants.add('ساروجا')
            variants.add('ساروج')

    # 4. معالجة الكلمات المركبة (دمج وفصل المسافات وإضافة/حذف التعريف للجزء الثاني)
    for v in list(variants):
        for cp in COMPOUND_PREFIXES:
            # حالة: "ابو رمانه" -> "ابورمانه"
            spaced = f"{cp} "
            if spaced in v:
                variants.add(v.replace(spaced, cp))
            # حالة: "ابورمانه" -> "ابو رمانه"
            joined_pattern = rf'\b{cp}(?=[ء-ي])'
            if re.search(joined_pattern, v):
                variants.add(re.sub(joined_pattern, f"{cp} ", v))

            # حالة: "باب سريجة" <-> "باب السريجة"
            m = re.search(rf'\b{cp}\s+(?:ال)?([ء-ي]+)', v)
            if m:
                base_word = m.group(1)
                variants.add(re.sub(rf'\b{cp}\s+(?:ال)?[ء-ي]+', f"{cp} {base_word}", v))
                variants.add(re.sub(rf'\b{cp}\s+(?:ال)?[ء-ي]+', f"{cp} ال{base_word}", v))
                variants.add(re.sub(rf'\b{cp}\s+(?:ال)?[ء-ي]+', f"{cp}{base_word}", v))
                variants.add(re.sub(rf'\b{cp}\s+(?:ال)?[ء-ي]+', f"{cp}ال{base_word}", v))

    # 5. معالجة أداة التعريف "الـ"
    for v in list(variants):
        tokens = v.split()
        # تجريد "الـ" من كل كلمة إذا كان طولها أكثر من 3 أحرف
        stripped_tokens = []
        for t in tokens:
            if t.startswith('ال') and len(t) > 3:
                stripped_tokens.append(t[2:])
            else:
                stripped_tokens.append(t)
        no_al_phrase = ' '.join(stripped_tokens)
        if len(no_al_phrase) >= 2:
            variants.add(no_al_phrase)

        # إضافة "الـ" للكلمة الأولى إذا كانت نكرة وليست من البوادئ المركبة
        if tokens and not tokens[0].startswith('ال') and len(tokens[0]) >= 3 and tokens[0] not in COMPOUND_PREFIXES:
            with_al = ['ال' + tokens[0]] + tokens[1:]
            variants.add(' '.join(with_al))

    # إرجاع كافة البدائل الفريدة المرتبة بالأطول أولاً مع استبعاد ما قل عن حرفين
    cleaned_list = sorted([x.strip() for x in variants if len(x.strip()) >= 2], key=lambda x: -len(x))
    return cleaned_list

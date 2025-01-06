import json
import os
import random
import re
import functools
from argparse import ArgumentParser
from multiprocessing import Pool

import jaconv
import regex

import sudachipy
from sudachipy import dictionary as sudachidict


def is_hiragana(c) -> bool:
    if c == "ゝ" or c == "ゞ" or c == "々":
        return False
    return u'\u3040' <= c <= u'\u309F'


def is_katakana(c):
    pattern = re.compile(r'^[\u30A0-\u30FF]+$')
    return bool(pattern.match(c))


def is_all_hiragana(s: str) -> bool:
    return all(is_hiragana(c) for c in s)


def is_all_alphanumeric_hyphen(s: str) -> bool:
    return re.search(r'^[a-zA-Z0-9\-]+$', s)


def is_hiragana_or_some_symbols(c) -> bool:
    if is_hiragana(c):
        return True
    if c in {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}:
        return True
    if re.match(r'[a-zA-Z-]', c):
        return True
    if c in {"ー","〜", "。", "・", "。", "、", "＆", "％", "&", "%", "$", "!", "！", "?", "？", "'"}:
        return True
    return False


def is_all_hiragana_or_some_symbols(s: str) -> bool:
    return all(is_hiragana_or_some_symbols(c) for c in s)


def has_kanji(s: str) -> bool:
    return re.search(r'[\u4e00-\u9faf]', s)


def is_kanji(c: str) -> bool:
    kanji_block = ('\u4e00' <= c <= '\u9fff')
    return kanji_block


def is_kanji_or_katakana(c) -> bool:
    if is_katakana(c):
        return True
    elif is_kanji(c):
        return True
    if c in {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}:
        return True
    return False        


def convert_token(token):
    surface = token[0]
    read = token[1]

    if surface == "『" and read == "」":
        read = "「"

    if surface == "は" and read == "わ":
        read = "は"
    if surface == "を" and read == "お":
        read = "を"
    if surface == "へ" and read == "え":
        read = "へ"

    if surface == "『":
        surface = "「"
    elif surface == "』":
        surface = "」"

    if surface in ["あるいは", "もしくは", "または", "もしくは", "では", "それでは", "おそらくは", "ついては", "こんにちは"]:
        read = surface

    if "ー" not in surface and "ー" in read:
        read = read.replace("ー", "う")

    # たまにreadに空白が入っていることがある
    read = read.replace(" ", "")

    if is_all_hiragana(surface):
#        if surface != read:
#            print("r:", read, "s:", surface)
        read = surface

    token[0] = surface
    token[1] = read

    return token


def proc_aozora_file(filename, token_limit=11):
    print(filename)
    result = []
    tokens = []

    skip = False

    for line in open(filename):
        line = line.rstrip()
        ss = line.split("\t")

        if line.startswith("行番号:"):
            if skip:
                skip = False
                tokens = []
            elif len(tokens) > 0 and len(tokens) < token_limit:
                surface, read, _ = zip(*tokens)

                if surface[-1] in {":", ".", "="}:
                    surface = list(surface)
                    read = list(read)

                    surface.pop()
                    read.pop()

                if surface[0] in {"総説", "特集"} or surface[-1] == "総説":
                    surface = []
                    read = []

                if len(surface) > 2:
                    sentence = {"surface": surface, "read": read}
                    result.append(sentence)
                tokens = []
            continue

        if len(ss) < 3:
            continue

        if ss[2] == "分かち書き":
            continue
        
        if ss[1] == "" and ss[0] in ["(", ")"]:
            ss[1] = ss[0]

        if ss[2] == "[入力 読み]" or ss[2] == "[入力文]":
            continue

        # どっちかが空になっている文は回復が難しい問題が含まれている割合が多いので捨てる
        if ss[0] == "" or ss[1] == "":
            skip = True
            continue

        ss = convert_token(ss)
        tokens.append(ss)

    if len(tokens) > 0:
        surface, read, _ = zip(*tokens)
        if len(surface) < 24:
            sentence = {"surface": surface, "read": read}
            result.append(sentence)
        tokens = []

    return result


def proc_aozora_dataset(dirname, output_dir, output_file, token_limit=11):
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, output_file)

    num_processes = 8
    pool = Pool(num_processes)

    files = []
    for root, dirs, filenames in os.walk(top=dirname):
        for filename in filenames:
            files.append(os.path.join(root, filename))

    proc_aozora_file_ = functools.partial(proc_aozora_file, token_limit=token_limit)

    print("file num:", len(files))

    with open(output_file, "w") as wfp:
        for results in pool.imap_unordered(proc_aozora_file_, files):
            for r in results:
                j = json.dumps(r, ensure_ascii=False)
                wfp.write(j)
                wfp.write("\n")

        # 以下は上のfor loopで置き換えられたが、上の並列ループ処理はdebugしづらいのでこちらもコメントとして残しておく
        # for root, dirs, files in os.walk(top=dirname):
        #     for f in files:
        #         filePath = os.path.join(root, f)
        #         print(filePath)
        #         r = proc_aozora_file(filePath, token_limit=token_limit)
        #         for x in r:
        #             j = json.dumps(x, ensure_ascii=False)
        #             wfp.write(j)
        #             wfp.write("\n")


def proc_anthy_file(filename):
    result = []

    i = 0
    for line in open(filename):
        i += 1
        if line.startswith("#"):
            continue

        line = line.rstrip()

        ss = line.split(" ")
        if len(ss) == 2:
            read = ss[0]
            surface = ss[1]
        elif len(ss) == 3:
            read = ss[1]
            surface = ss[2]
            print(read)
            print(surface)
            print("---")

        read = read.split("|")
        surface = surface.split("|")

        if len(read) != len(surface):
            print(i, read, surface)

        assert(len(read) == len(surface))

        read = list(filter(lambda x: x != "", read))
        surface = list(filter(lambda x: x != "", surface))

        print(read)

        sentence = {"surface": surface, "read": read}
        result.append(sentence)

    return result

def proc_anthy_dataset(dirname, output_dir, output_file):
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, output_file)

    with open(output_file, "w") as wfp:
        for root, dirs, files in os.walk(top=dirname):
            for f in files:
                # corpus.4.txtは変換誤りの記録なので、スキップする
                if f == "corpus.4.txt":
                    continue
                if f.endswith(".txt"):
                    filePath = os.path.join(root, f)
                    print(filePath)
                    r = proc_anthy_file(filePath)
                    for x in r:
                        j = json.dumps(x, ensure_ascii=False)
                        wfp.write(j)
                        wfp.write("\n")


def proc_cannadic_file(filename):
    result = []

    i = 0
    for line in open(filename):
        i += 1
        if line.startswith("#"):
            continue

        line = line.rstrip()

        print(line)
        ss = line.split(" ")

#        print(ss)
        score = 100
        read = ss[0]

        read = read.replace("あいのさときょいくだい", "あいのさときょういくだい")

        for x in ss[1:]:
            if x.startswith("#") and re.search(r".*\d+$", x):
                print(x.split("*"))
                score = int(x.split("*")[1])
                print("score:", score)
                continue

            surface = x

#            if len(surface) >= 4:
#                continue

            if read in {"きりるもじ", "ぎりしゃもじ"}:
                continue

            sentence = {"surface": surface, "read": read, "score": score}
            print(sentence)
            result.append(sentence)

    return result


def proc_alt_cannadic(dirname, output_dir, output_file):
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, output_file)

    with open(output_file, "w") as wfp:
        for root, dirs, files in os.walk(top=dirname):
            for f in files:
                if f.endswith(".ctd"):
                    filePath = os.path.join(root, f)
                    print(filePath)
                    r = proc_cannadic_file(filePath)
                    for x in r:
                        j = json.dumps(x, ensure_ascii=False)
                        wfp.write(j)
                        wfp.write("\n")



sudachi_tokenizer = sudachidict.Dictionary(dict="full").create()

def katakana_to_hiragana(text):
    # カタカナをひらがなに変換する
    def _convert(match):
        katakana = match.group()
        hiragana = ''.join([chr(ord(katakana[i])-96) for i in range(len(katakana))])
        return hiragana

    # 正規表現でカタカナを検索して置換する
    pattern = r'[\u30a1-\u30f6]+'
    return re.sub(pattern, _convert, text)

def parse_furigana_result(text):
    mode = "out"
    skip_read = False

    r_surface = []
    r_read = []

    for c in text:
        if c == "{":
            mode = "in_word"
            continue
        elif mode == "in_word" and c == "/":
            mode = "in_read"
            continue
        elif mode == "in_read" and c == "}":
            mode = "out"
            skip_read = False
            continue

        if mode == "out":
            r_surface.append(c)
            r_read.append(c)
        elif mode == "in_word" and c.isdigit():
            r_surface.append(c)
            r_read.append(c)
            skip_read = True
        elif mode == "in_word":
            r_surface.append(c)
        elif mode == "in_read" and not skip_read:
            r_read.append(c)

    return "".join(r_surface), katakana_to_hiragana("".join(r_read))


def calc_freq_threshold(filename):
    filename = os.path.basename(filename)
    n = int(filename[0])

    if n == 1 or n == 2:
        return 500
    elif n == 3:
        return 300
    elif n >= 4:
        return 200


def parse_japanese_web_ngram_line(line, freq_threshold):
    ngram, freq = line.split("\t")

    freq = int(freq)
    if freq < freq_threshold:
        return None

    if re.search("[:|()（）「」【】『』><\[\]\"〔〕〇┃┣☆∪├←∟×↑└∩⊂“★◎●▶□△○│≪≫◇▲↓→»▼▽※■◆]", ngram):
        return None

    if re.search("、", ngram) and random.random() > 0.001:
        return None

    if regex.search("^(\p{hiragana}{1,2}|\p{katakana}{1})$", ngram):
        return None

    ngram = ngram.split(" ")

    if ngram[0][0] in {"~", "(", ")", "/", ":", "'", "$", "&","+", "=", ";", "@", "?", ",", "#", "`", "%", "「", "『", "」", "』", "（", "）", "-", "、", "・", "〜", "*", "─", "〈", "《", "〉", "》", "”", "♪", "−", "⇒"}:
        return None

    ngram = "".join(ngram)

    ngram = ngram.replace("<S>", "")
    ngram = ngram.replace("</S>", "")

    if freq < 2500 and re.search(r"^(たのは|たとき|のは|ときゃ|って|おきたい|たくて|たくない|たくは|たくなる|っ|して|うと)", ngram):
        return None

    if re.search(r'^[のはがをとにて][ア-ン][ーア-ン]+', ngram):
        if random.random() > 0.05:
            #                    print("skip", ngram)
            return None

    if regex.search(r'^(ちまった|かかった|なかった|ちゃった|はたった|でたった|たかった|にたった|のたった|れるって|かどっち|いねっと|もどっち|わくば).{0,2}', ngram):
        return None

    if is_all_alphanumeric_hyphen(ngram):
#        print("skip by is_all_alphanumeric_hyphen", ngram)
        return None

    if len(ngram) == 0:
        return None

    # 版画以外に"版"ではじまるngramは要らなさそう
    if len(ngram) > 1 and ngram[0] == "版" and ngram[1] != "画":
        return None
    # 以下の条件を満たすやつはあんま重要じゃなさそうなので確率的に省く
    elif len(ngram) > 4 and ngram[-1] in {"は", "が", "の", "と", "を"} and is_kanji_or_katakana(ngram[-2]):
        if random.random() > 0.05:
            #                    print("skip", ngram)
            return None
    # 以下の条件を満たすやつはあんま重要じゃなさそうなので確率的に省く
    elif len(ngram) > 2 and ngram[0] in {"は", "が", "の", "と", "を", "に"} and is_kanji_or_katakana(ngram[1]):
        if random.random() > 0.05:
            #                    print("skip", ngram)
            return None
    elif len(ngram) > 1 and ngram[-2] in {"を"}:
        return None
    elif ngram[-1] in {"/", ":", "-"}:
        return None
    # 以下はスパムの痕跡っぽいので捨てる
    elif "馬鹿冨" in ngram:
        return None
    # 以下はスパムの痕跡っぽいので捨てる
    elif "醴醴醴" in ngram:
        return None

    elif re.search("^00+(-*)[円人]", ngram):
        return None

    if ngram.startswith("v") or ngram.endswith("v") or ngram.startswith("w") or ngram.endswith("w"):
        return None

    # アルファベットが2文字以上入っていたら捨てる
    if re.search(r"[A-Za-z]{2,}", ngram):
        return None

    # なくても変換精度に影響なさそうなものを捨てる
    if regex.search(r"^[A-Za-z0-9-]+$", ngram):
        return None

    # なくても変換精度に影響なさそうなものを捨てる
    if regex.search(r"^\p{Han}[〜&%-]", ngram):
        return None

    # なくても変換精度に影響なさそうなものを捨てる
    if regex.search(r"^\p{Han}$", ngram):
        return None

    # なくても変換精度に影響なさそうなものを捨てる
    if freq > 100000 and len(ngram) < 3:
        return None
    elif freq > 100000 and regex.search(r"^(\p{Han}{1,4}|\p{hiragana}{1,4}|p{katakana}{1,4})$", ngram):
        return None

    # なくても変換精度に影響なさそうなものを捨てる
    if re.search(r'[^0-9]\d+$', ngram):
        return None

    # なくても変換精度に影響なさそうなものを捨てる
    if re.search(r'[&\"\'@:-]$', ngram):
        return None

    # 変なngramを捨てる
    if regex.search(r'^[たちさすぬねきくけこばびぶべぼぱぴぷぺぽパピプペポ]\p{Han}', ngram) and "行" not in ngram:
        return None

    # 変なngramを捨てる
    if regex.search(r'(と底|[てには]関)$', ngram):
        return None

    # 変なngramを捨てる
    if regex.search(r'^[零〇一壱二弐三参四五六七八九拾]第', ngram):
        return None

    if re.search(r'^完全無料', ngram):
        return None

    if re.search(r'^一人一|一人一$', ngram):
        return None

    if re.search(r'^.(ホテル|旅館|温泉|銀行|医院|病院|美容室|女学院|女子大学|大学)$', ngram):
        return None

    if ngram == "御礼申上" or ngram == "御礼申し上":
        return None

    # 救うのが難しすぎるので捨てる
    if re.search(r'^[12]人\d', ngram):
        return None

    if re.search(r'[なにをがはもで][一二三四五六七八0-9A-Za-z]+$', ngram):
        return None

    if re.search(r"年生.+", ngram):
        return None

    if re.search(r"^(題の|testtest)", ngram):
        return None

    if re.search(r"[^・](・|・・)$", ngram):
        return None

    if re.search(r"(・・・・|ーーー)", ngram):
        return None

    if re.search(r"^て\d$", ngram):
        #            print("skip", ngram, read)
        return None

    if re.search(r"^ー", ngram):
        return None

    if re.search(r"(てい|てご|もい)$", ngram):
        return None

    if regex.search(r"^こと\p{han}.+", ngram):
        return None

    # 間に合う/間にあう 以外は捨てる
    if re.search(r"^間に[^合あ][うっいわ]", ngram):
        return None

    if re.search(r"([^(寒|急|保|水|空)]冷|[^制防]御|[^次落]第)$", ngram):
        return None

    if re.search(r"[^(りん|たま|ごご)]ご$", ngram):
        return None

    if regex.search(r"[^(て|で|に|って|で|て|\p{Han})]はい$", ngram):
        return None

    if re.search(r"[^(フェニックスの|だ|じゃ|ひとし)]お$", ngram):
        return None

    if re.search(r"^.{2,}でい$", ngram):
        return None

    if re.search(r"(のお|住ん|かかっ)$", ngram):
        return None

    if regex.search(r"\p{Hiragana}[住狂捕]$", ngram):
        return None

    if regex.search(r"^([えとうのを]|のを|のが|のに|のか|のお)\p{hiragana}{5,}", ngram):
        return None

    if regex.search(r"^(とおなじ|とおなか)", ngram):
        return None

#    if regex.search(r"^と\p{hiragana}{3,}", ngram): and not re.search(r"^(とんでも|とって|とこ|とんぼ|とんねるず)", ngram):
#        return None

    if regex.search(r"^な[^いくか]\p{hiragana}{4,}", ngram):
        return None

    if re.search(r"いない暦|お湯お湯お湯|あーあーあー|死ね死ね死ね|で美$", ngram):
        return None

    if re.search(r"^(.{3,}会員登録|会員登録.{3,})$", ngram):
        return None

    if re.search(r"^(.+ログイン無料|ログイン無料.+)$", ngram):
        return None

    if re.search(r"^(.+トラックバック一覧|トラックバック一覧.+)$", ngram):
        return None

    if re.search(r"^(.+投稿コメント|投稿コメント.+)$", ngram):
        return None

    if re.search(r"^(.+(ブログ|サイト)ランキング|(ブログ|サイト)ランキング.+)$", ngram):
        return None

    if re.search(r"ランキングをもっと見る", ngram):
        return None

    if re.search(r"くにくにくに", ngram):
        return None

    if regex.search(r'^用\p{Han}{2,}$', ngram):
        if not re.search(r'^用(務|宗|心|水|語|量|字|意)', ngram):
            return None

    a = ngram[0]
    if len(ngram) > 3 and all(c == a for c in ngram):
        return None

    if freq < 2500 and re.search(r"送料無料", ngram):
        return None

    # 単語の途中で切れてるやつを捨てる
    if re.search(r"^(都キャンペーン|ちぃ地球|貫光殺砲|先など|々|おさん|おさん[^ぽ])", ngram):
        return None

    if re.search(r"^年(法|[零〇一壱二弐三参四五六七八九拾]月)$", ngram):
        return None

    if regex.search(r'^.{1,2}・・・', ngram):
        return None

    if re.search(r".{5,}[^予契制解条規節集確成特公誓密要]約$", ngram):
        return None

    if regex.search(r'^(\p{Han}|\p{Hiragana}|・|ー){2,}等$', ngram):
        if not re.search(r'^[平同高中]等$', ngram):
            return None

    # if "龍" in ngram and "竜" in ngram:
    #     return None

    r = sudachi_tokenizer.tokenize(ngram, sudachipy.Tokenizer.SplitMode.C)

    surface = []
    read = []
    for x in r:
#        print(x)
        surface_ = x.surface()
        reading_form = x.reading_form()
        surface.append(surface_)
        if re.match(r"^\d+$", surface_):
            read.append(surface_)
        elif re.match(r"^[A-Z]+$", surface_):
            read.append(surface_)
        elif reading_form == "キゴウ" and not regex.match(r"\p{han}+|きごう", surface_):
            read.append(surface_)
        else:
            read.append(jaconv.kata2hira(reading_form))

    surface = "".join(surface)
    read = "".join(read)

    #r = dict_reader.furigana(dbert_prediction)
    #surface, read = parse_furigana_result(r)

    if surface != ngram:
        print("orig:", ngram, "surface:", surface, "r:", r)

    if "龍" in ngram:
        surface = surface.replace("竜", "龍")

    if len(surface) == 0:
        return None

    # 解析ミスを救うアドホックな処理
    read = read.replace("魅音", "みおん")
    read = read.replace("激奏", "げきそう")
    read = read.replace("激萌え", "げきもえ")
    read = read.replace("激萎え", "げきなえ")
    read = read.replace("筑駒", "つくこま")
    read = read.replace("諂媚", "てんび")
    read = read.replace("剱岳", "つるぎだけ")
    read = read.replace("はやいものかち", "はやいものがち")
    read = read.replace("毒々", "どくどく")
    read = read.replace("爆速", "ばくそく")
    read = read.replace("爆速", "ばくそく")
    read = read.replace("爆あげ", "ばくあげ")
    read = read.replace("爆あがり", "ばくあがり")
    read = read.replace("爆食い", "ばくぐい")
    read = read.replace("爆もり", "ばくもり")
    read = read.replace("爆かち", "ばくがち")
    read = read.replace("爆売れ", "ばくうれ")
    read = read.replace("潮りゅう", "ちょうりゅう")
    read = read.replace("笑ぅ", "わらぅ")
    read = read.replace("ご送", "ごそう")
    read = read.replace("きぬの禰", "きふね")
    read = read.replace("阿紫はな", "あしはな")
    read = read.replace("奴ぁ", "やつぁ")
    read = read.replace("おにたろう", "きたろう")
    read = read.replace("おうけとりあと", "おうけとりご")
    read = read.replace("おうけとりあと", "おうけとりご")
    read = read.replace("ふんやろう", "くそやろう")
    read = read.replace("いっぽうなら", "ひとかたなら")

    if "律" in surface:
        read = read.replace("ただしっちゃん", "りっちゃん")

    if "九龍" in surface:
        read = read.replace("きゅうりゅう", "くーろん")

    if "世は情け" in surface:
        read = read.replace("せいはなさけ", "よはなさけ")

    if "気に入って" in surface:
        read = read.replace("きにはいって", "きにいって")

    if "明日" in surface:
        read = read.replace("あすなか", "あすじゅう")

        if "明日香" not in surface and "明日菜" not in surface:
            if random.random() > 0.5:
                read = read.replace("あす", "あした")

    if "明後日" in surface:
        if random.random() > 0.5:
            read = read.replace("みょうごにち", "あさって")

    if "貸した金" in surface and "かしたきん" in read:
        read = read.replace("かしたきん", "かしたかね")

    if "お追従" in surface:
        read = read.replace("おついじゅう", "おついしょう")

    if "追従を許さない" in surface:
        return None

    if "借りた金" in surface and "かりたきん" in read:
        read = read.replace("かりたきん", "かりたかね")

    if "亞人" in surface and "あにん" in read:
        read = read.replace("あにん", "あじん")

    if "三軒茶屋" in surface and "みのきちゃや" in read:
        if random.random() > 0.5:
            read = read.replace("みのきちゃや", "さんげんぢゃや")
        else:
            read = read.replace("みのきちゃや", "さんげんじゃや")

    if re.search(r"お家[^元騒芸]", surface) and "おいえ" in read:
        if random.random() > 0.5:
            read = read.replace("おいえ", "おうち")

    if re.search(r"った金$", surface) and "ったきん" in read:
        read = read.replace("ったきん", "ったかね")

    if re.search(r"鈴の音", surface) and "すずのおと" in read:
        read = read.replace("すずのおと", "すずのね")

    if "大勢を占め" in surface:
        read = read.replace("おおぜいをしめ", "たいせいをしめ")

    if "一回" in surface:
        read = read.replace("いちかい", "いっかい")

    if "我が物顔" in surface:
        read = read.replace("わがものかお", "わがものがお")

    if "口角泡を" in surface:
        read = read.replace("こうかくほうを", "こうかくあわを")

    if "堪忍袋の緒" in surface:
        read = read.replace("かんにんぶくろのいとぐち", "かんにんぶくろのお")

    if "否が応でも" in surface:
        read = read.replace("いながおうでも", "いやがおうでも")

    if "相半ば" in surface:
        read = read.replace("しょうなかば", "あいなかば")

    if "小一時間" in surface:
        read = read.replace("さいちじかん", "こいちじかん")

    if re.search(r'(ちりめん|チリメン|粒|粉|実|花)山椒', surface):
        read = read.replace("さんしょう", "ざんしょう")

    if re.search(r"^風に舞う", surface):
        read = read.replace("ふうにまう", "かぜにまう")

    if "福神漬け" in surface:
        if random.random() > 0.5:
            read = read.replace("ふくじんつけ", "ふくじんづけ")
        else:
            read = read.replace("ふくじんつけ", "ふくしんづけ")

    if "一日中" in surface:
        if re.search(r'一日中(雨|晴れ|曇り|寝)*[あ-んア-ン]*$', surface):
            read = read.replace("いちにちちゅう", "いちにちじゅう")
            read = read.replace("いちにちなか", "いちにちじゅう")
            read = read.replace("いちにっちゅうう", "いちにちじゅうあめ")
            print("replaced:", surface, read)
        elif re.search(r'一日中2', surface):
            read = read.replace("いちにち2", "いちにちじゅう2")

    if "遅漏" in surface:
        read = read.replace("おそろう", "ちろう")

    if "気味" in surface:
        if re.search(r'[^不薄]気味', surface):
            read = read.replace("きみ", "ぎみ")

    if "一時の恥" in surface:
        read = read.replace("いちじのはじ", "いっときのはじ")

    if "一時" in surface:
        if re.search(r'(幸せ[なの]*|安らぎ|[春夏秋冬]の|楽しい)一時', surface):
            read = read.replace("いちじ", "ひととき")
        if re.search(r'^一時を', surface):
            read = read.replace("いちじ", "ひととき")
        elif re.search(r'^一時の', surface):
            read = read.replace("いちじ", "いっとき")

    if regex.search(r'^堂に入\p{hiragana}', surface):
        read = read.replace("どうにはい", "どうにい")

    if re.search(r'気に入る', surface):
        read = read.replace("きにはいる", "きにいる")

    if re.search(r'お腹が空いた', surface):
        read = read.replace("おなかがあいた", "おなかがすいた")

    if re.search(r'浅草寺', surface):
        read = read.replace("あさくさてら", "せんそうじ")

    if re.search(r'^中[123][あ-んア-ン]$', surface):
        if re.search(r'^[123]$', read):
            read = "ちゅう" + read
            print("ちゅう：", read)

    if re.search(r'中[123]', surface):
        # {"surface": "岐阜中2", "read": "ぎふ2"}のように、なぜか「中」のよみが消えるケースがある
        if not re.search(r'(ちゅう|なか|じゅう)', read):
            #                print("drop:", surface, read)
            return None

    if "来場所" in surface and "らいじょうしょ" in read:
        read = read.replace("らいじょうしょ", "らいばしょ")

    if "他言無用" in surface and "たげんむよう" in read:
        read = read.replace("たげんむよう", "たごんむよう")

    if "大夫" in surface and "だいぶ" in read:
        read = read.replace("らいじょうしょ", "らいばしょ")

    if surface == "大夫の監":
        read = "たいふのげん"
    elif surface == "修理の大夫":
        read = "すりのかみ"

    if surface.startswith("良い"):
        if random.random() > 0.95:
            read = read.replace("よい", "いい")

    if "私" in surface and "わたくし" in read:
        if "私立" not in surface:
            if random.random() > 0.5:
                read = read.replace("わたくし", "わたし")

    if "御礼申" in surface and "おれいもう" in read:
        if random.random() > 0.33:
            read = read.replace("おれい", "おんれい")

    if "満員御礼" in surface and "まんいんおれい" in read:
        read = read.replace("まんいんおれい", "まんいんおんれい")

    if regex.search(r"(\p{Hiragana}頬[をに]|[のなたが]頬)$", surface) and "ほお" in read:
            read = read.replace("ほお", "ほほ")

    if regex.search(r"(V6|V字|バトラーV|Vジャンプ|クエストV|仕事人V|ボルテスV)", surface) and "ぼると" in read:
            read = read.replace("ぼると", "ぶい")

    if regex.search(r"後知恵", surface) and "ごちえ" in read:
            read = read.replace("ごちえ", "あとぢえ")

    if "御社" in surface and "ごしゃ" in read:
        read = read.replace("ごしゃ", "おんしゃ")

    if "頬を" in surface:
        if random.random() > 0.5:
            read = read.replace("ほおを", "ほほを")

    if "麻疹" in surface and ("蕁麻疹" not in surface):
        if random.random() > 0.5:
            read = read.replace("ましん", "はしか")

    if "灰燼" in surface and "帰" in surface:
        read = read.replace("かえ", "き")

    if "猫の額" in surface and "ねこのがく" in read:
        read = read.replace("ねこのがく", "ねこのひたい")

    if re.search(r"額に.*(手|汗|浮)", surface) and "がく" in read:
        read = read.replace("がく", "ひたい")

    if re.search(r"一月(程|ほど|半|前|以上|以内|を経|ぶり|足らず|遅れ|くらい前)", surface) and "いちがつ" in read:
        read = read.replace("いちがつ", "ひとつき")

    if re.search(r"(起算して|あと|ここ|ほんの|それから)一月", surface) and "いちがつ" in read:
        read = read.replace("いちがつ", "ひとつき")

    if re.search(r"二月(程|ほど|半|前|以上|以内|を経|ぶり|足らず|遅れ|くらい前)", surface) and "にがつ" in read:
        read = read.replace("にがつ", "ふたつき")

    if re.search(r"(起算して|あと|ここ|ほんの|それから)二月", surface) and "にがつ" in read:
        read = read.replace("にがつ", "ふたつき")

    if re.search(r"三月(程|ほど|半|前|以上|以内|を経|ぶり|足らず|遅れ|くらい前)", surface) and "さんがつ" in read:
        read = read.replace("さんがつ", "みつき")

    if re.search(r"(起算して|あと|ここ|ほんの|それから)三月", surface) and "さんがつ" in read:
        read = read.replace("さんがつ", "みつき")

    if "言う" in surface:
        if random.random() > 0.5:
            read = read.replace("ゆう", "いう")

    if "いちとう" in read and "一頭" in surface:
        read = read.replace("いちとう", "いっとう")

    if "馬頭観音" in surface:
        read = read.replace("ばとうかんのん", "めずかんのん")

    if "穴が開く" in surface and "毛" not in surface:
        read = read.replace("あながひらく", "あながあく")

    if "万霊" in surface:
        read = read.replace("まんれい", "ばんれい")

    if "牛頭馬頭" in surface:
        read = read.replace("ごずばとう", "ごずめず")

    # 10万、とかのよみで「まん」が消えることがある
    if re.search(r'\d万$', surface) and "まん" not in read:
           read = read + "まん"

    if re.search(r'\d万', surface) and "まん" not in read:
        return None

    # 10億、とかのよみで「おく」が消えることがある
    if re.search(r'\d億$', surface) and "おく" not in read:
           read = read + "おく"

    if re.search(r'\d億', surface) and "おく" not in read:
        return None

    # １人、のよみで「にん」が消える
    if re.search(r'1人1人', surface) and "ひとりひとり" not in read:
           read = read.replace("11", "ひとりひとり")
    elif re.search(r'[^\d]1人$', surface):
           read = read.replace("1", "ひとり")
    elif re.search(r'[^\d]1人', surface):
        return None
    elif re.search(r'[^\d]2人$', surface):
           read = read.replace("2", "ふたり")
    elif re.search(r'[^\d]2人', surface):
        return None
    elif re.search(r'\d人$', surface) and "にん" not in read:
           read = read + "にん"

    # 1日のよみで「にち」が消える
    if re.search(r'1日', surface) and "にち" not in read:
           read = read.replace("1", "1にち")

    if re.search(r'1次選考', surface) and "じせんこう" not in read:
           read = read.replace("1", "1じせんこう")

    if re.search("^第1", surface):
        return None

    if surface == "羽田空港第1ビル":
        read = "はねだくうこうだい1ビル"
    elif surface == "羽田空港第1ビル駅":
        read = "はねだくうこうだい1ビル駅"


    if re.search(r'(1|6|0)匹', surface) and "ひき" in read:
           read = read.replace("ひき", "ぴき")

    if re.search(r'3匹', surface) and "ひき" in read:
           read = read.replace("ひき", "びき")

    # A3, A4など
    if "$A\d" in surface and "あーる" in read:
        read = read.replace("あーる", "えー")

    if "A級" in surface and "あーるきゅう" in read:
        read = read.replace("あーるきゅう", "えーきゅう")

    if "A種" in surface and "あーるしゅ" in read:
        read = read.replace("あーるしゅ", "えーしゅ")

    if regex.search(r"^糞[^尿便詰づ食掃]", surface) and "ふん" in read:
            read = read.replace("ふん", "くそ")

    if "既存" in surface and "きそん" in read:
        if random.random() > 0.66:
            read = read.replace("きそん", "きぞん")  # "きぞん"も許容する

    if "裏面" in surface and "りめん" in read:
        if random.random() > 0.66:
            read = read.replace("りめん", "うらめん")  # "うらめん"も許容する

    if "鼻血" in surface and "はなじ" in read:
        if random.random() > 0.33:
            read = read.replace("はなじ", "はなぢ")  # 昭和61年7月1日告示の「現代仮名遣い」では「はなぢ」と書くことになっている

    if "近々" in surface and "ちかじか" in read:
        if random.random() > 0.33:
            read = read.replace("ちかじか", "ちかぢか")  # 昭和61年7月1日告示の「現代仮名遣い」では「ちかぢか」と書くことになっている

    if "馬肥ゆ" in surface and "うまこえゆ" in read:
        if random.random() > 0.33:
            read = read.replace("うまこえゆ", "うまこゆ")

    if "三鼎" in surface and "さんかなえ" in read:
        read = read.replace("さんかなえ", "みつがなえ")

    if "火風鼎" in surface and "かふうかなえ" in read:
        read = read.replace("かふうかなえ", "かふうてい")

    if regex.search(r"\p{Han}不足", surface) and "ふそく" in read:
            read = read.replace("ふそく", "ぶそく")

    if regex.search(r"(\p{han}|\p{katakana})会社", surface) and "かいしゃ" in read:
            read = read.replace("かいしゃ", "がいしゃ")

    if regex.search(r"\p{Han}喧嘩", surface) and "けんか" in read:
            read = read.replace("けんか", "げんか")

    if regex.search(r"\p{Hiragana}位\p{Hiragana}*$", surface) and "くらい" in read:
        if random.random() > 0.5:
            read = read.replace("くらい", "ぐらい")

    if regex.search(r"\p{Hiragana}両端\p{Hiragana}*$", surface) and "りょうたん" in read:
        if random.random() > 0.8:
            read = read.replace("りょうたん", "りょうはし")
        elif random.random() > 0.8:
            read = read.replace("りょうたん", "りょうはじ")

    if re.search(r"大公(妃|領|宮)", surface) and "だいこう" in read:
        if random.random() > 0.5:
            read = read.replace("だいこう", "たいこう")

    if re.search(r"大公園", surface) and "てごんうぉん" in read:
        read = read.replace("てごんうぉん", "だいこうえん")

    if re.search(r"高原", surface) and "こうぉん" in read:
        read = read.replace("こうぉん", "こうげん")

    if re.search(r"花園", surface) and "ふぁうぉん" in read:
        read = read.replace("ふぁうぉん", "はなぞの")

    if re.search(r"江原", surface) and "えばら" in read:
        if random.random() > 0.5:
            read = read.replace("えばら", "えはら")

    if re.search(r"芥子醤油", surface) and "けししょうゆ" in read:
            read = read.replace("けししょうゆ", "からししょうゆ")

    if re.search(r"肝醤油", surface) and "かんしょうゆ" in read:
            read = read.replace("かんしょうゆ", "きもじょうゆ")

    if re.search(r"淡口醤油", surface) and "あわぐち" in read:
            read = read.replace("あわぐち", "うすくち")

    if re.search(r"(興味|信心|奥|意義|感慨|味わい|印象|思い出|山|注意|慈悲|慎み|つつしみ)深", surface) and "ふか" in read:
            read = read.replace("ふか", "ぶか")

    if re.search(r"(出汁|刺し身|刺身|芥子|生姜|砂糖|酢)醤油", surface) and "しょうゆ" in read:
        if random.random() > 0.5:
            read = read.replace("しょうゆ", "じょうゆ")

    if re.search(r"(いつ|何時)の間に", surface) and "いつのあいだに" in read:
        read = read.replace("いつのあいだに", "いつのまに")

    if re.search(r"凹んで", surface) and "へこんで" in read:
        if random.random() > 0.75:
            read = read.replace("へこんで", "くぼんで")

    if "鼎の軽重" in surface and "かなえのけいじゅう" in read:
        read = read.replace("かなえのけいじゅう", "かなえのけいちょう")
    elif "軽重を問" in surface and "けいじゅうをと" in read:
        read = read.replace("けいじゅうをと", "けいちょうをと")

    if "弘法筆" in surface and "ぐほうひつ" in read:
        read = read.replace("ぐほうひつ", "こうぼうふで")


    if re.search(r'[^\d]\d本', surface):
        read = read.replace("2ぽん", "2ほん")
        read = read.replace("3ぽん", "3ぼん")
        read = read.replace("4ぽん", "4ほん")
        read = read.replace("5ぽん", "5ほん")
        read = read.replace("7ぽん", "7ほん")
        read = read.replace("9ぽん", "9ほん")

    if re.search(r'\d人$', surface) and ("にん" not in read and "ひとり" not in read):
           read = read + "にん"

    if "ひとりひとりにん" in read:
        return None    

    if regex.search(r"\p{Hiragana}生$", surface) and read.endswith("なま"):
        return None

    if regex.search(r"^([なえとうのを]|のを|のが|のに|のか|のお)\p{Han}", surface) and not re.search(r"う蝕|感じ|漢字", surface):
        return None

    if regex.search(r'(\p{Hiragana}+日本中|日本中\p{Hiragana}+)$', surface) and "にっぽんちゅう" in read:
        if random.random() > 0.5:
            read = read.replace("にっぽんちゅう", "にほんじゅう")
        else:
            read = read.replace("にっぽんちゅう", "にっぽんじゅう")

    if regex.search(r'(\p{Hiragana}+日本[人語]|日本[人語]\p{Hiragana}+)$', surface) and "にっぽん" in read:
        if random.random() > 0.5:
            read = read.replace("にっぽん", "にほん")

    if regex.search(r'(\p{Hiragana}+日本|日本\p{Hiragana}+)$', surface) and "にっぽん" in read:
        if random.random() > 0.5:
            read = read.replace("にっぽん", "にほん")

    if regex.search(r'(\p{Hiragana}+西日本|西日本\p{Hiragana}+)$', surface) and "にっぽん" in read:
        read = read.replace("にっぽん", "にほん")

    # 連濁しない和語の一側面, 呂建輝, 2020 によると、仕立ては常に連濁する
    if regex.search(r'(小説|映画|劇|小物|振袖|手縫い|味|鍋|風|塩|麹|味噌|みそ|しょうゆ|すまし|きもの|単衣|比翼|正絹|総裏|\p{Katakana}|ー)仕立て', surface) and "したて" in read:
        read = read.replace("したて", "じたて")

    if regex.search(r'(キッチン|刈り込み|刈込|剪定|園芸|美容|花|金)鋏', surface) and "はさみ" in read:
        read = read.replace("はさみ", "ばさみ")

    if regex.search(r'(勉強|学習|スチール|パソコン|事務|執務)机', surface) and "つくえ" in read:
        read = read.replace("つくえ", "づくえ")

    if re.search(r'^言う', surface) and re.search(r'^ゆう', read):
        read = read.replace("ゆう", "いう")

    if re.search(r'言う$', surface) and re.search(r'ゆう$', read):
        read = read.replace("ゆう", "いう")

    if re.search(r'使い勝手', surface) and "つかいかって" in read:
        read = read.replace("つかいかって", "つかいがって")

    if re.search(r'大枚.*叩', surface) and "たた" in read:
        read = read.replace("たたく", "はたく")
        read = read.replace("たたい", "はたい")

    if re.search(r'三分の理', surface) and "さんぶんのり" in read:
        read = read.replace("さんぶんのり", "さんぶのり")

    if re.search(r"材料出尽くし", surface) and "ざいりょうでづくし" in read:
        read = read.replace("でいりょうでづくし", "ざいりょうでつくし")

    if re.search(r"ステーキ宮", surface) and "すてーきぐう" in read:
        read = read.replace("すてーきぐう", "すてーきみや")

    if re.search(r"蛇が出る", surface) and "へびがでる" in read:
        read = read.replace("へびがでる", "じゃがでる")

    if re.search(r"大手を(振っ|ふっ)", surface) and "おおてをふっ" in read:
        read = read.replace("おおてをふっ", "おおでをふっ")

    if regex.search(r"\p{Katakana}宮$", surface) and regex.search(r"\p{Katakana}ぐう$", read):
        read = read.replace("ぐう", "きゅう")

    if re.search(r"一言.*二言", surface) and "言語" not in surface:
        read = read.replace("にごん", "ふたこと")

    if re.search(r"二言(め|目|交)", surface):
        read = read.replace("にごん", "ふたこと")

    if re.search(r"名は体", surface):
        read = read.replace("なはからだ", "なはたい")

    if re.search(r"共存共栄", surface):
        # きょうそん のほうが本則っぽい
        if random.random() > 0.33:
            read = read.replace("きょうぞんきょうえい", "きょうそんきょうえい")

    if re.search(r"県人$", surface) and re.search(r"けんにん$", read):
        read = read.replace("けんにん", "けんじん")

    if re.search(r"錦上花", surface) and re.search(r"きんじょうげ", read):
        read = read.replace("きんじょうげ", "きんじょうはな")

    if re.search(r"(長|香)宗我部", surface) and re.search(r"そがべ", read):
        # そがべの人もいるらしいので全部は置き換えない
        if random.random() > 0.33:
            read = read.replace("そがべ", "そかべ")

    if re.search(r"研究所", surface) and re.search(r"けんきゅうしょ", read):
        if random.random() > 0.33:
            read = read.replace("けんきゅうしょ", "けんきゅうじょ")

    if surface == "貝覆い" and read == "かい":
        read = "かいおおい"

    # 処理がややこしいので捨てる、間違いが混入するよりはよい
    if "貝覆い" in surface and "かいおおい" not in read:
        return None

    # 鮎川義介は「あいかわ」とよむが、ほかは「あゆかわ」に直す
    if re.search(r'鮎川[^義]', surface) and re.search(r'あいかわ', read):
        read = read.replace("あいかわ", "あゆかわ")

    if re.search(r'魔貫光殺砲', surface) and re.search(r'まかんこうさつほう', read):
        read = read.replace("まかんこうさつほう", "まかんこうさっぽう")

    if re.search(r'並盛', surface) and re.search(r'なみさかん', read):
        read = read.replace("なみさかん", "なみもり")

    if re.search(r'三方(よし|良し)', surface) and re.search(r'みかたよし', read):
        read = read.replace("みかたよし", "さんぽうよし")

    if re.search(r'お三方', surface) and re.search(r'おさんほう', read):
        read = read.replace("おさんほう", "おさんかた")

    if regex.search(r'^弥栄\p{Hiragana}', surface) and re.search(r'^やさか', read):
        read = read.replace("やさか", "いやさか")

    if re.search(r'並盛中', surface) and re.search(r'なみもりなか', read):
        read = read.replace("なみもりなか", "なみもりちゅう")

    if re.search(r'一本背負', surface) and re.search(r'いちぽんせおい', read):
        read = read.replace("いちぽんせおい", "いっぽんぜおい")

    if re.search(r'七難', surface) and re.search(r'なななん', read):
        read = read.replace("なななん", "しちなん")

    # なぜか「頼み」の部分のよみがなが抜ける
    if re.search(r'神頼み', surface) and not re.search(r'(た|だ)のみ', read):
        read = read.replace("かみ", "かみだのみ")

    if re.search(r'通好み', surface) and re.search(r'つうこうみ', read):
        read = read.replace("つうこうみ", "つうごのみ")

    if regex.search(r'\p{Han}通り', surface) and re.search(r'とおり', read) and not re.search(r'[御一]通り', surface):
        read = read.replace("とおり", "どおり")

    if re.search(r'夢見心地', surface) and re.search(r'ゆめみここち', read):
        read = read.replace("ゆめみここち", "ゆめみごこち")

    if re.search(r'熱っちぃ', surface) and re.search(r'ほてっちぃ', read):
        read = read.replace("ほてっちぃ", "あっちぃ")

    if re.search(r'者魂', surface) and re.search(r'たましい', read):
        read = read.replace("たましい", "だましい")

    if re.search(r'川端', surface) and re.search(r'かわはた', read):
        if random.random() > 0.5:
            read = read.replace("かわはた", "かわばた")

    if re.search(r'^(もう|)年も年', surface):
        read = read.replace("としもねん", "としもとし")
        read = read.replace("ねんもとし", "としもとし")

    if re.search(r'三文', surface) and re.search(r'さんぶん', read):
        read = read.replace("さんぶん", "さんもん")

    if re.search(r'門前市', surface) and re.search(r'もんぜんし', read):
        read = read.replace("もんぜんし", "もんぜんいち")

    if re.search(r'(人|あなた|私|自分|女性|男性|茶人|味|通|ツウ)好み', surface):
        read = read.replace("このみ", "ごのみ")

    if re.search(r'吟醸山廃', surface) and "ぎんじょうさんはい" in read:
        read = read.replace("ぎんじょうさんはい", "ぎんじょうやまはい")

    if re.search(r'腹(が|も)空[くい]', surface):
        read = read.replace("らがあ", "らがす")

    if re.search(r'崖線', surface):
        read = read.replace("がけせん", "がいせん")

    if re.search(r'頂門の一針', surface) and "ちょうもんのいちはり" in read:
        read = read.replace("ちょうもんのいちはり", "ちょうもんのいっしん")

    # 連濁しない和語の一側面, 呂建輝, 2020 によると、仕立ては常に連濁する
    if regex.search(r'(味|鍋|風|塩|麹|味噌|みそ|吟醸|梅|かめ|瓶)仕込み', surface) and "しこみ" in read:
        read = read.replace("しこみ", "じこみ")

    if re.search(r"^(廃|次|段)仕込み", surface):
        return None

    if re.search(r"^条第", surface):
        return None

    # if "こうじょうのがつ" in read:
    #     return None

    # if "ひゃひゃひゃ" in read:
    #     return None

    if re.search(r"^[ぁぃぅぇぉゃゅょ]", read):
        return None

    # 七五三が途中で切れている
    if re.search(r"^五三", surface):
        return None

    if re.search(r'^(者魂|離する)$', surface):
        return None

    if re.search(r"^(\d|\,)+([円人年匹本個千万億兆つ分名回日時月枚点番週〜年%条歳回第社位階]|種類|世紀|トン|キロ|km|cm|時間|盗賊)", surface):
        if random.random() > 0.1:
            return None

    if re.search(r".+甘$", surface):
        return None

    if regex.search(r"\p{Hiragana}+[辛大少小高低見来観出入好急同診不勝負思]$", surface) and not re.search(r"(申し|思い)出", surface):
        return None

    if re.search(r".+(容疑者|被害者)$", surface):
        return None

    # たまに、解析できない場合によみがなに漢字が残る場合がある
    if not is_all_hiragana_or_some_symbols(read):
        #            print("has_kanj:", surface, read)
        return None

    if len(surface) > 9 and re.search(r"(ござ|ござい|ございま|ございまし|お願いし|出品さ|なっ|お待ちし|ませ|守ら|またご|しまし|負わ|行っ|まっ|たん)$", surface):
        return None

    if len(surface) > 15 and regex.search(r"\p{Han}", surface) and not regex.search(r"\p{Hiragana}", surface):
        return None

    # 変なフレーズを捨てる
    if regex.search(r"^(\p{Hiragana}|\p{Katakana}|[0-9A-Za-z]){12,}$", surface):
        return None

    # 長いやつも捨てる
    #if regex.search(r"^(\p{Hiragana}|\p{Katakana}|\p{Han}|[0-9A-Za-z]){16,}$", surface):
    #    return None
    if len(surface) > 16:
        return None


    r = {"surface": surface, "read": read, "freq": freq}
    return r

def count_kanji(s):
    r = 0
    for c in s:
        if regex.match("\p{Han}", c):
            r += 1
    return r

score_pattern1 = re.compile(r"(新着|スタークラブ|ログインして|利用規約|特定商取引法|プライバシーポリシー|会員のみ|クリック|トラックバック|コメント|公開無料|リンクに追加|更新情報|取引法に基づく|ブロとも|へのトラック|へスキップ|無断転載|ブログ村|リンクフリー|マイリスト|お気に入りに.|このブログ|記事.トラック|さんのブログ|いるクレジットカード|ニュース遊都|パスワードを忘れた|ブログ管理|ページ(の)*(先頭|トップ).|ボタンを押して|メールアドレスを入力|保証するもの.|無料今すぐ)")

def calc_score(x):
    freq = x["freq"]
    surface = x["surface"]
    read = x["read"]

    score = freq * (len(surface) ** 0.3333)

    if regex.search(r"[A-Za-z]・", surface):
        score = score * 0.25

    if regex.search(r"$[A-Za-z0-9]", surface):
        score = score * 0.25

    # if regex.search(r"^(\p{Hiragana}{1,1}|\p{Katakana}{1,1})$", surface):
    #     score = (score / 1000) ** 0.5 * 1000
    #     score = score * 0.5
    if regex.search(r"^(\p{Hiragana}|\p{Katakana}){1}$", surface):
        score = score * 0.01
    if regex.search(r"^(\p{Hiragana}|\p{Katakana}){2}$", surface):
        score = score * 0.1
    elif regex.search(r"^(\p{Hiragana}{3}|\p{Katakana}{3})$", surface):
        score = score * 0.2
    elif regex.search(r"^\p{Hiragana}{4,}$", surface):
        score = score * 0.5
    elif regex.search(r"^\p{Katakana}{4,}$", surface):
        score = score * 0.33
    elif regex.search(r"^(\p{Katakana}|ー){2,4}\p{Han}{1,3}$", surface):
        score = score * 5

    if regex.search(r"^\p{Han}{1,4}$", surface):
        score = score * 5
    elif regex.search(r"^\p{Han}は$", surface):
        score = score * 5
    elif regex.search(r"^\p{Han}{1,3}\p{katakana}{2,4}", surface):
        score = score * 5
    elif regex.search(r"^\p{Han}{1,4}(する|しい)$", surface):
        score = score * 10
    elif regex.search(r"^\p{Han}{3}す$", surface):
        score = score * 5
    elif regex.search(r"^\p{Han}{1,3}[にのをは]\p{Han}{1,3}$", surface):
        score = score * 10
    elif regex.search(r"^.{1,3}[にのを]\p{Han}.{1,3}$", surface):
        score = score * 10
    elif regex.search(r"^.{1,5}\p{hiragana}(点|天)$", surface):
        score = score * 10
    elif regex.search(r"^(文節|分節|以外|意外|制約|誓約|製薬|成約|返って|却って|帰って|同額|同学|旅|度|回避|会費|高速|拘束|行っ|言っ|紅顔|睾丸|厚顔|抗癌|炒め|痛め|傷め|いため|先頭|戦闘|銭湯|尖塔|試料|資料|飼料).{1,3}$", surface):
        score = score * 5
    elif regex.search(r"^組み換え|組み合わせ", surface):
        score = score * 10
    elif regex.search(r"^.{1,3}(至急|支給|至急|子宮|四球|始球|死球)$", surface):
        score = score * 5
    elif re.search(r"上り", surface) and re.search(r"あがり", read):
        score = score * 0.1
    elif re.search(r"読替え|読取り|読取る|読返し|[読振絞話乗駆飛取張投押落突書申差]込ん", surface):
        score = score * 0.1

    if score_pattern1.search(surface):
        score = score * 0.1

    if re.search(r"^(思います|お問い合わせ|思い|問い合わせ|人|中|下さい|ページ|ください)$", surface):
        score = score * 0.1

    if score > 50000:
        score = ((score / 50000) ** 0.25) * 250
    else:
        score = ((score / 50000) ** 0.9) * 250

    if len(surface) == 2 and count_kanji(surface) == 2:
        score = ((score / 250) ** 0.5) * 500
    elif len(surface) == 4 and count_kanji(surface) > 3:
        score = ((score / 250) ** 0.5) * 500
    elif len(surface) == 3 and count_kanji(surface) == 3:
        score = ((score / 250) ** 0.5) * 500

    if score == 0:
        score = 1

    return int(score)


def proc_japanese_web_ngram_file(filename):
    result = []
    freq_threshold = calc_freq_threshold(filename)

    i = 0

    for line in open(filename):
        i += 1

        if i % 100000 == 0:
            print(filename, i)
           
        line = line.rstrip()

        r = parse_japanese_web_ngram_line(line, freq_threshold)

        if r:
            score = calc_score(r)
            if score < 20:
                continue
            r["score"] = score
            result.append(r)

    return result

def proc_japanese_web_ngram_dataset(dirname, output_dir, output_file):
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, output_file)

    files = []
    for root, dirs, filenames in os.walk(top=dirname):
        for filename in filenames:
            if re.search(r"\dgm-\d\d\d\d", filename):
#            if re.search(r"1gm-\d\d\d\d", filename):
                files.append(os.path.join(root, filename))

    num_processes = 4
    pool = Pool(num_processes)

    with open(output_file, "w") as wfp:
        for results in pool.imap_unordered(proc_japanese_web_ngram_file, files):
            for r in results:
                j = json.dumps(r, ensure_ascii=False)
                wfp.write(j)
                wfp.write("\n")

#                wfp.write(r)
#                wfp.write("\n")

    # with open(output_file, "w") as wfp:
    #     for root, dirs, files in os.walk(top=dirname):
    #         for f in files:
    #             filePath = os.path.join(root, f)
    #             print(filePath)
    #             r = proc_japanese_web_ngram_file(filePath)
    #             for x in r:
    #                 j = json.dumps(x, ensure_ascii=False)
    #                 wfp.write(j)
    #                 wfp.write("\n")


def main():
    # r = parse_japanese_web_ngram_line("あいまい\t307414", 100)
    # print(r)
    # print(calc_score(r))

    # r = parse_japanese_web_ngram_line("週休２日制\t2501", 100)
    # print(r)
    # print(calc_score(r))

    # r = parse_japanese_web_ngram_line("裸族	25642", 100)
    # print(r)
    # print(calc_score(r))

    # r = parse_japanese_web_ngram_line("全統マーク模試\t900", 100)
    # print(r)
    # print(calc_score(r))

    # r = parse_japanese_web_ngram_line("全統マーク\t1534", 100)
    # print(r)
    # print(calc_score(r))


    # r = parse_japanese_web_ngram_line("功罪 相 半ば	1070", 100)
    # print(r)
    # print(calc_score(r))

    # r = parse_japanese_web_ngram_line("獲物に追従する\t2501", 100)
    # print(r)
    # print(calc_score(r))


    # r = parse_japanese_web_ngram_line("転職祝い金\t2501", 100)
    # print(r)
    # print(calc_score(r))

    # r = parse_japanese_web_ngram_line("三文 の 得\t12000", 100)
    # print(r)
    # print(calc_score(r))

    # r = parse_japanese_web_ngram_line("1ムラウチドットコム本館へ\t20004", 100)
    # print(r)
    # print(calc_score(r))

    # r = parse_japanese_web_ngram_line("あざみの駅\t294", 100)
    # print(r)
    # print(calc_score(r))

    arg_parser = ArgumentParser(add_help=False)

    arg_parser.add_argument("--output", default="dataset", type=str, help="output directory path")
    args = arg_parser.parse_args()

    proc_aozora_dataset("dataset/shosi_dataset", args.output, "shosi.json")
    proc_aozora_dataset("dataset/aozora_dataset", args.output, "aozora.json", token_limit=32)

    #proc_anthy_dataset("dataset/anthy-corpus", args.output, "anthy.json")
    #proc_alt_cannadic("dataset/alt-cannadic", args.output, "alt-cannadic.json")
    
    proc_japanese_web_ngram_dataset("dataset/japanese-web-ngram", args.output, "nwn.json")

if __name__ == "__main__":
    main()

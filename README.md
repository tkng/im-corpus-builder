# Japanese input method corpus builder

## これはなに？

日本語のふりがな付きのコーパスを作るためのスクリプトです。

download.shでダウンロードを行い、prepare_dataset.pyで使いやすい形式に変換処理等を行います。

```
bash download.sh
uv run python prepare_dataset.py
```

`prepare_dataset.py`は、ルールベースである程度の振り仮名の修正を行います。

## ライセンス

本ソースコードはMITライセンスです。元データのライセンスについては元データのサイトで確認してください。

## 元データ

- [ndl\-lab/huriganacorpus\-aozora: 青空文庫及びサピエの点字データから作成した振り仮名コーパスのデータセット](https://github.com/ndl-lab/huriganacorpus-aozora)
- [ndl\-lab/huriganacorpus\-ndlbib: 全国書誌データから作成した振り仮名のデータセット](https://github.com/ndl-lab/huriganacorpus-ndlbib)
- [N\-gram コーパス \- 日本語ウェブコーパス 2010](https://www.s-yata.jp/corpus/nwc2010/ngrams/)

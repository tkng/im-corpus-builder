#!/bin/bash

output_dir="dataset"     # ダウンロード先のディレクトリ

mkdir -p "$output_dir"

curl https://lab.ndl.go.jp/dataset/huriganacorpus/shosi_dataset.zip -o "${output_dir}/shosi_dataset.zip"
curl https://lab.ndl.go.jp/dataset/huriganacorpus/aozora_dataset.zip -o "${output_dir}/aozora_dataset.zip"
curl https://s3-ap-northeast-1.amazonaws.com/nwc2010-ngrams/word/over99/filelist -o /tmp/filelist

# ファイルリストからURLを読み込んでダウンロード
while IFS= read -r url; do
  if [ -n "$url" ]; then
    echo "Downloading $url..."
    curl -o "${output_dir}/japanese-web-ngram/$(basename "$url")" "$url"
  fi
done < /tmp/filelist

unzip dataset/aozora_dataset.zip -d dataset
unzip dataset/shosi_dataset.zip -d dataset

find . -name "${output_dir}/*.xz" -print0|xargs xz -0 -d 

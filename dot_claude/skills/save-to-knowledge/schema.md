# Knowledge(s) database schema

Database page: https://app.notion.com/p/d2ded9d1cc1b42bd9b1dd3c2d97ce7a3
Data source ID (use this as the `notion-create-pages` parent):
`ebb90a48-79c1-43bf-903c-5c1c192051ab`

Last confirmed against the live schema: 2026-09-07. If a create call rejects a property or option
below as unrecognized, the schema has drifted — re-fetch the data source and update this file.

## Properties to set

| Property | Type | Notes |
|---|---|---|
| `Name` | title | Required. Short, specific — not a generic label. |
| `Description` | text | One sentence, sub-title length. |
| `カテゴリ` | select | Exactly one. Options below. |
| `大ジャンル` | multi_select | Usually exactly one. Options below. |
| `中ジャンル` | multi_select | Usually one, occasionally two. Options below. |
| `わたしtag` | multi_select | Zero or more. Options below. |
| `userDefined:URL` | url | Optional — only if the finding centers on one external resource. |

Leave `Created` alone (auto-set). Leave `サブアイテム`, `親アイテム`, and the competitive-programming
relation property alone unless the user explicitly asks to link this entry to another Knowledge(s)
page or postmortem.

## カテゴリ (pick one)

決定事項, 好み・価値観, プロジェクト・文脈, 人物・関係性, エピソード・気づき, ワークフロー・ツール,
就活, 研究

For a technical workaround, config discovery, or tool workflow (the common case for a Claude Code
session), use ワークフロー・ツール.

## 大ジャンル (usually one)

テクノロジー, 経済・ビジネス, 社会・暮らし, 政治・国際, 健康・医療, 文化・アート, エンタメ, スポーツ,
学習・キャリア

## 中ジャンル (usually one, occasionally two)

言葉の解説, AI・人工知能, 機械学習・ディープラーニング, データサイエンス, ソフトウェア開発,
Web制作・デザイン, SaaS・クラウドサービス, サイバーセキュリティ, ブロックチェーン・暗号資産,
ガジェット・ハードウェア, スマートフォン（iPhone/Android）, PC・自作PC, VR / AR / MR,
IoT（モノのインターネット）, 宇宙開発, 経営・マネジメント, 起業・スタートアップ, マーケティング,
セールス・営業, 広告・ブランディング, 金融・ファイナンス, 株式投資・資産運用, 不動産, 税金・会計,
業界動向・レポート, M&A・事業承継, 人事・HR, ロジスティクス・サプライチェーン, EC・ネットショップ,
働き方・ワークライフバランス, ライフハック・暮らしの知恵, 環境問題・SDGs, エネルギー問題,
教育・子育て, ジェンダー・多様性, 地域活性化・まちづくり, 交通・モビリティ, 住宅・インテリア,
ファッション, 食・料理, 防災・防犯, ペット, 国内政治, 国際情勢, 選挙, 外交・安全保障, 社会保障,
法律・制度, 人権問題, 地方自治, 医療・ヘルスケア, 予防医学, メンタルヘルス,
フィットネス・トレーニング, 栄養学・食事法, 睡眠, 介護・福祉, 公衆衛生, 読書・書籍, デザイン・意匠,
美術・博物館, 現代アート, 建築, 歴史, 哲学・思想, 伝統文化, 写真・カメラ, 映画・ドラマ, 音楽,
アニメ・漫画, ゲーム, 舞台・演劇, お笑い・バラエティ, YouTube・配信, ラジオ・ポッドキャスト, 野球,
サッカー, バスケットボール, テニス, 格闘技, モータースポーツ, オリンピック・国際大会, eスポーツ,
キャリアデザイン・転職, 自己啓発, スキルアップ, 資格取得, 語学学習, 生産性向上・効率化,
リーダーシップ, プレゼンテーション, 副業・フリーランス, 書評・アウトプット術

For a Claude Code / development-tooling finding, ソフトウェア開発 is the usual fit. For a hardware
or OS-level config finding (like an Everything/PC search quirk), PC・自作PC can fit better than
ソフトウェア開発 — judge by what the finding is actually about, not the tool category.

## わたしtag (zero or more)

わたしの製作, めも, 本, わたしの考え, 知見, 試してみたこと, 記事にした, わたし自身, DailyAlpaca,
競プロ postmortem

A workaround or fix that was tried and confirmed working in-session is 試してみたこと. A durable
insight worth remembering on its own is 知見. These two are not mutually exclusive.

## Example call shape

```
notion-create-pages({
  parent: { type: "data_source_id", data_source_id: "ebb90a48-79c1-43bf-903c-5c1c192051ab" },
  pages: [{
    properties: {
      "Name": "...",
      "Description": "...",
      "カテゴリ": "ワークフロー・ツール",
      "大ジャンル": ["テクノロジー"],
      "中ジャンル": ["ソフトウェア開発"],
      "わたしtag": ["試してみたこと"]
    },
    content: "- bullet one\n- bullet two"
  }]
})
```

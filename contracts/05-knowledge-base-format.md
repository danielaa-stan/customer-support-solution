# 05. База знань для RAG (контракт C → B)

C створює файли, B індексує їх. Зміст чисел береться з [04-business-rules.md](04-business-rules.md).

## Політики: `data/policies/*.md`

Один файл = один документ. Ім'я файлу = `doc_id` + `.md` (напр. `refund-policy.md`).
Перелік обов'язкових документів і розділів: див. таблицю в 04.

Формат:

```markdown
---
doc_id: refund-policy
title: Політика повернення коштів
version: 1.0
---

## 2.1 Вікно повернення
Повернення можливе протягом 14 днів з дати списання ...

## 2.2 Подвійне списання
Якщо ми списали кошти двічі ...
```

Правила:

1. Заголовок розділу має вигляд `## <номер> <назва>`. Номер = якір для цитування.
2. Формат цитати (`policy_ref`): `doc_id#номер`, напр. `refund-policy#2.1`.
3. Один розділ: 2–6 речень, самодостатній (без «див. вище»), бо B розбиває документ на чанки за розділами.
4. Мова документів: українська.

B повертає з `search_policy` об'єкти `{doc_id, section, title, text, policy_ref}`.

## Схожі кейси: `data/cases.json`

Масив із ≥ 150 вирішених кейсів (ціль 200). Формат елемента:

```json
{
  "case_id": "case_0042",
  "title": "Скасування через ціну, утримано знижкою",
  "intent": "cancel_subscription",
  "reason": "price_too_high",
  "plan": "individual",
  "customer_message": "Для мене стало дорого, хочу скасувати.",
  "summary": "Клієнт слухав 35 год/міс. Запропоновано discount_50_3m, прийнято.",
  "actions": [
    {"tool": "get_available_offers", "args": {}},
    {"tool": "apply_retention_offer", "args": {"offer_code": "discount_50_3m"}}
  ],
  "resolution": "retained",
  "policy_refs": ["retention-rules#1.1"],
  "tags": ["price", "discount"]
}
```

- `intent`, `reason`, `resolution`: значення з enum у [06](06-transcript-and-analysis.md).
- `actions[].tool`: лише реальні назви інструментів із [03](03-mcp-tools.md).
- Розподіл кейсів має бути реалістичним: приблизно 30% скасування, 25% білінг, 15% refund, 15% техніка, 10% зміна плану, 5% інше.
- B індексує для пошуку текст `title + customer_message + summary`.

## Контракт зі сторони B

B гарантує: агент у відповіді про рішення посилається щонайменше на один `policy_ref`, коли виконує дію з правилом
(refund, cancel, пропозиція утримання).

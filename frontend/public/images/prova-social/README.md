# 🖼️ Imagens de Prova Social

Esta pasta contém as imagens de prova social (prints, depoimentos, antes/depois) usadas no Funil Longo.

## 📁 Arquivos Esperados

### Imagens do Funil Longo (Etapa de Dores)

Após o áudio de diagnóstico de dores (`02-dor-generica.opus` ou variantes), o sistema envia uma sequência de imagens de prova social.

**Arquivos mapeados:**
- `00000018.jpg` (ou `.png`)
- `00000019.jpg`
- `00000020.jpg`
- `00000021.jpg`
- `00000022.jpg`
- `00000023.jpg`
- `00000024.jpg`
- `00000025.jpg`

**Total:** 8 imagens

## 🔄 Quando São Enviadas

1. Lead descreve sua situação/dor
2. Sistema envia áudio de diagnóstico (`02-dor-generica.opus`)
3. Sistema envia sequência de imagens (00000018 até 00000025)
4. Sistema envia texto: "Me conta aqui gata, o que tá faltando pra tu dar esse passo?"

## 📝 Tipos de Conteúdo

As imagens podem conter:
- **Antes e depois** de transformações
- **Prints de treino** da Paloma
- **Cards do corpo** treinando
- **Depoimentos** de clientes
- **Provas sociais** diversas

## 🔧 Como Adicionar Novas Imagens

1. **Coloque o arquivo** nesta pasta
2. **Use nome descritivo** ou mantenha código original do WhatsApp
3. **Atualize** o código que referencia essas imagens
4. **Formato recomendado:** `.jpg`, `.png`, `.webp`

## 📊 Referência no Código

As imagens são referenciadas no código através de:

```typescript
// Em data/audios.ts - TEXT_TEMPLATES
life_funil_longo_prova_social: {
  images: ["00000018", "00000019", ..., "00000025"]
}
```

**Caminho completo:** `/images/prova-social/00000018.jpg`

---

**Última atualização:** 2025-01-XX


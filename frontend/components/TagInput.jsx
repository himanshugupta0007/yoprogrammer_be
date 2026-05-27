import { useState } from "react";

const TAG_TYPES = ["general", "project", "domain", "lang"];

const TAG_COLORS = {
  project: { bg: "#dbeafe", border: "#93c5fd", label: "#1d4ed8" },
  domain:  { bg: "#dcfce7", border: "#86efac", label: "#15803d" },
  lang:    { bg: "#fef9c3", border: "#fde047", label: "#854d0e" },
  general: { bg: "#f3f4f6", border: "#d1d5db", label: "#374151" },
};

function TagChip({ tag, onRemove }) {
  const color = TAG_COLORS[tag.type] ?? TAG_COLORS.general;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "3px 10px",
        borderRadius: 999,
        fontSize: 13,
        background: color.bg,
        border: `1px solid ${color.border}`,
        color: color.label,
      }}
    >
      <span style={{ opacity: 0.6, fontSize: 11 }}>{tag.type}</span>
      <span>{tag.value}</span>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          style={{
            marginLeft: 2,
            border: "none",
            background: "none",
            cursor: "pointer",
            color: "inherit",
            padding: 0,
            lineHeight: 1,
            fontSize: 14,
          }}
          aria-label={`Remove ${tag.type}:${tag.value}`}
        >
          ×
        </button>
      )}
    </span>
  );
}

export function TagInput({ tags = [], onChange, maxTags = 10 }) {
  const [type, setType] = useState("general");
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  function addTag(e) {
    e.preventDefault();
    setError("");

    const v = value.trim().toLowerCase();
    if (!v) return;
    if (v.length > 50) {
      setError("Tag must be 50 characters or fewer");
      return;
    }
    if (tags.length >= maxTags) {
      setError(`Maximum ${maxTags} tags allowed`);
      return;
    }
    if (tags.some((t) => t.type === type && t.value === v)) {
      setError("Tag already added");
      return;
    }

    onChange([...tags, { type, value: v }]);
    setValue("");
  }

  function removeTag(index) {
    onChange(tags.filter((_, i) => i !== index));
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {/* Existing tag chips */}
      {tags.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {tags.map((tag, i) => (
            <TagChip key={i} tag={tag} onRemove={() => removeTag(i)} />
          ))}
        </div>
      )}

      {/* Input row */}
      <form onSubmit={addTag} style={{ display: "flex", gap: 6 }}>
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13 }}
        >
          {TAG_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <input
          value={value}
          onChange={(e) => { setValue(e.target.value); setError(""); }}
          placeholder={
            type === "project" ? "e.g. yoprogrammer" :
            type === "domain"  ? "e.g. algorithms" :
            type === "lang"    ? "e.g. python" :
                                 "e.g. interview-prep"
          }
          style={{
            flex: 1,
            padding: "6px 10px",
            borderRadius: 6,
            border: "1px solid #d1d5db",
            fontSize: 13,
          }}
        />

        <button
          type="submit"
          disabled={tags.length >= maxTags}
          style={{
            padding: "6px 14px",
            borderRadius: 6,
            border: "none",
            background: "#3b82f6",
            color: "#fff",
            cursor: tags.length >= maxTags ? "not-allowed" : "pointer",
            fontSize: 13,
          }}
        >
          Add
        </button>
      </form>

      {error && <span style={{ fontSize: 12, color: "#dc2626" }}>{error}</span>}
    </div>
  );
}

export { TagChip };

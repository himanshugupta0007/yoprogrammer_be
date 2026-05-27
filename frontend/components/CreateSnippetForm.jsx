import { useState } from "react";
import { TagInput } from "./TagInput";

const API_URL = import.meta.env.VITE_API_URL; // e.g. https://xxx.execute-api.ap-south-1.amazonaws.com/dev

const INITIAL_FORM = {
  title: "",
  code: "",
  language: "",
  notes: "",
  tags: [],
};

export function CreateSnippetForm({ token, onCreated }) {
  const [form, setForm] = useState(INITIAL_FORM);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function set(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/snippets`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: token,
        },
        body: JSON.stringify({
          title: form.title,
          code: form.code,
          language: form.language,
          notes: form.notes,
          tags: form.tags, // [{type, value}, ...]
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.message ?? "Failed to create snippet");
        return;
      }

      setForm(INITIAL_FORM);
      onCreated?.(data);
    } catch (err) {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 600 }}>
      <div>
        <label style={labelStyle}>Title *</label>
        <input
          value={form.title}
          onChange={(e) => set("title", e.target.value)}
          placeholder="e.g. Binary search"
          required
          style={inputStyle}
        />
      </div>

      <div>
        <label style={labelStyle}>Language *</label>
        <input
          value={form.language}
          onChange={(e) => set("language", e.target.value)}
          placeholder="e.g. python"
          required
          style={inputStyle}
        />
      </div>

      <div>
        <label style={labelStyle}>Code *</label>
        <textarea
          value={form.code}
          onChange={(e) => set("code", e.target.value)}
          placeholder="Paste your code here..."
          required
          rows={8}
          style={{ ...inputStyle, fontFamily: "monospace", resize: "vertical" }}
        />
      </div>

      <div>
        <label style={labelStyle}>Notes / Gotchas / Explanation</label>
        <textarea
          value={form.notes}
          onChange={(e) => set("notes", e.target.value)}
          placeholder="e.g. Use lo + (hi-lo)//2 to avoid overflow on mid calculation..."
          rows={3}
          style={{ ...inputStyle, resize: "vertical" }}
        />
      </div>

      <div>
        <label style={labelStyle}>Tags</label>
        <p style={{ fontSize: 12, color: "#6b7280", marginBottom: 6 }}>
          Categorize by <strong>project</strong>, <strong>domain</strong>, <strong>lang</strong>, or <strong>general</strong>
        </p>
        <TagInput tags={form.tags} onChange={(tags) => set("tags", tags)} />
      </div>

      {error && (
        <div style={{ padding: "8px 12px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 6, color: "#dc2626", fontSize: 13 }}>
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        style={{
          padding: "10px 20px",
          background: loading ? "#93c5fd" : "#3b82f6",
          color: "#fff",
          border: "none",
          borderRadius: 6,
          fontSize: 14,
          fontWeight: 600,
          cursor: loading ? "not-allowed" : "pointer",
        }}
      >
        {loading ? "Saving..." : "Save Snippet"}
      </button>
    </form>
  );
}

const labelStyle = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  color: "#374151",
  marginBottom: 4,
};

const inputStyle = {
  width: "100%",
  padding: "8px 10px",
  border: "1px solid #d1d5db",
  borderRadius: 6,
  fontSize: 14,
  boxSizing: "border-box",
};

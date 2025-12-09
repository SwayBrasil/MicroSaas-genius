// frontend/src/pages/Products.tsx
import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { listProducts, type Product } from "../api";

export default function Products() {
  const location = useLocation();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);

  useEffect(() => {
    // Extrai filtro de source da URL
    const params = new URLSearchParams(location.search);
    const source = params.get("source");
    setSourceFilter(source);
    loadProducts(source || undefined);
  }, [location.search]);

  async function loadProducts(source?: string) {
    try {
      setLoading(true);
      setError(null);
      const data = await listProducts(source);
      setProducts(data);
    } catch (err: any) {
      console.error("Erro ao carregar produtos:", err);
      setError(err?.message || "Erro ao carregar produtos");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: "center" }}>
        <div>Carregando produtos...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <div style={{ color: "var(--danger)", marginBottom: 16 }}>Erro: {error}</div>
        <button className="btn" onClick={loadProducts}>
          Tentar novamente
        </button>
      </div>
    );
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: "0 0 8px 0" }}>Produtos</h1>
          <p style={{ color: "var(--muted)", margin: 0 }}>
            {sourceFilter === "eduzz" 
              ? "Produtos sincronizados da Eduzz" 
              : sourceFilter === "themembers"
              ? "Produtos sincronizados da The Members"
              : "Produtos disponíveis (Eduzz e The Members)"}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className={!sourceFilter ? "btn" : "btn soft"}
            onClick={() => loadProducts()}
            style={{ fontSize: 13 }}
          >
            Todos
          </button>
          <button
            className={sourceFilter === "eduzz" ? "btn" : "btn soft"}
            onClick={() => loadProducts("eduzz")}
            style={{ fontSize: 13 }}
          >
            Eduzz
          </button>
          <button
            className={sourceFilter === "themembers" ? "btn" : "btn soft"}
            onClick={() => loadProducts("themembers")}
            style={{ fontSize: 13 }}
          >
            The Members
          </button>
        </div>
      </div>

      {products.length === 0 ? (
        <div style={{ padding: 48, textAlign: "center", color: "var(--muted)" }}>
          <div>Nenhum produto encontrado</div>
          <div style={{ fontSize: 14, marginTop: 8 }}>
            Os produtos serão sincronizados automaticamente quando houver vendas
          </div>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 16 }}>
          {products.map((product) => (
            <div
              key={product.id}
              className="card"
              style={{
                padding: 20,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ flex: 1 }}>
                <h3 style={{ margin: "0 0 8px 0" }}>{product.title}</h3>
                <div style={{ display: "flex", gap: 16, fontSize: 14, color: "var(--muted)", flexWrap: "wrap", alignItems: "center" }}>
                  <span>ID: {product.external_product_id}</span>
                  {product.source && (
                    <span
                      style={{
                        padding: "2px 8px",
                        borderRadius: 4,
                        background: product.source === "eduzz" ? "rgba(59, 130, 246, 0.15)" : "rgba(139, 92, 246, 0.15)",
                        color: product.source === "eduzz" ? "#3b82f6" : "#8b5cf6",
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    >
                      {product.source === "eduzz" ? "Eduzz" : product.source === "themembers" ? "The Members" : product.source}
                    </span>
                  )}
                  {product.type && <span>Tipo: {product.type}</span>}
                  {product.status && (
                    <span
                      style={{
                        padding: "2px 8px",
                        borderRadius: 4,
                        background:
                          product.status === "active"
                            ? "rgba(34, 197, 94, 0.15)"
                            : "rgba(239, 68, 68, 0.15)",
                        color: product.status === "active" ? "#22c55e" : "#ef4444",
                        fontSize: 12,
                        fontWeight: 600,
                      }}
                    >
                      {product.status}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// frontend/src/pages/ContactDetail.tsx
import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  getContactByThread,
  getContact,
  updateContact,
  addContactTag,
  removeContactTag,
  addContactNote,
  deleteContactNote,
  createContactReminder,
  updateContactReminder,
  getContactSubscriptionStatus,
  getContactSubscriptions,
  getContactSales,
  type Contact,
  type ContactTag,
  type ContactNote,
  type ContactReminder,
  type SubscriptionStatus,
  type Subscription,
  type ContactSales,
} from "../api";

export default function ContactDetail() {
  const { threadId } = useParams<{ threadId: string }>();
  const navigate = useNavigate();
  const [contact, setContact] = useState<Contact | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [newTag, setNewTag] = useState("");
  const [newNote, setNewNote] = useState("");
  const [newReminder, setNewReminder] = useState({ message: "", dueDate: "" });
  const [subscriptionStatus, setSubscriptionStatus] = useState<SubscriptionStatus | null>(null);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [loadingSubscription, setLoadingSubscription] = useState(false);
  const [contactSales, setContactSales] = useState<ContactSales | null>(null);
  const [loadingSales, setLoadingSales] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (!threadId) return;
    loadContact();
  }, [threadId]);

  async function loadContact() {
    if (!threadId) return;
    try {
      setLoading(true);
      const c = await getContactByThread(Number(threadId));
      setContact(c);
      // Carrega status de assinatura e vendas
      if (c.id) {
        loadSubscriptionStatus(c.id);
        loadContactSales(c.id);
      }
    } catch (error: any) {
      console.error("Erro ao carregar contato:", error);
      // Tenta criar se não existir
      if (error?.response?.status === 404) {
        // O backend cria automaticamente, tenta novamente
        setTimeout(loadContact, 500);
      }
    } finally {
      setLoading(false);
    }
  }

  async function loadSubscriptionStatus(contactId: number) {
    try {
      setLoadingSubscription(true);
      const [status, subs] = await Promise.all([
        getContactSubscriptionStatus(contactId),
        getContactSubscriptions(contactId),
      ]);
      setSubscriptionStatus(status);
      setSubscriptions(subs);
    } catch (error) {
      console.error("Erro ao carregar assinatura:", error);
      setSubscriptionStatus(null);
      setSubscriptions([]);
    } finally {
      setLoadingSubscription(false);
    }
  }

  async function loadContactSales(contactId: number) {
    try {
      setLoadingSales(true);
      const sales = await getContactSales(contactId);
      setContactSales(sales);
    } catch (error) {
      console.error("Erro ao carregar vendas:", error);
      setContactSales(null);
    } finally {
      setLoadingSales(false);
    }
  }

  async function handleUpdate(field: string, value: any) {
    if (!contact) return;
    try {
      const updated = await updateContact(contact.id, { [field]: value });
      setContact(updated);
      setEditing(null);
    } catch (error) {
      console.error("Erro ao atualizar:", error);
    }
  }

  async function handleAddTag() {
    if (!contact || !newTag.trim()) return;
    try {
      await addContactTag(contact.id, newTag.trim());
      await loadContact();
      setNewTag("");
    } catch (error) {
      console.error("Erro ao adicionar tag:", error);
    }
  }

  async function handleRemoveTag(tagId: number) {
    if (!contact) return;
    try {
      await removeContactTag(contact.id, tagId);
      await loadContact();
    } catch (error) {
      console.error("Erro ao remover tag:", error);
    }
  }

  async function handleAddNote() {
    if (!contact || !newNote.trim()) return;
    try {
      await addContactNote(contact.id, newNote.trim());
      await loadContact();
      setNewNote("");
    } catch (error) {
      console.error("Erro ao adicionar nota:", error);
    }
  }

  async function handleDeleteNote(noteId: number) {
    if (!contact) return;
    try {
      await deleteContactNote(contact.id, noteId);
      await loadContact();
    } catch (error) {
      console.error("Erro ao deletar nota:", error);
    }
  }

  async function handleCreateReminder() {
    if (!contact || !newReminder.message.trim() || !newReminder.dueDate) return;
    try {
      await createContactReminder(contact.id, newReminder.message, newReminder.dueDate);
      await loadContact();
      setNewReminder({ message: "", dueDate: "" });
    } catch (error) {
      console.error("Erro ao criar lembrete:", error);
    }
  }

  async function handleToggleReminder(reminderId: number, completed: boolean) {
    if (!contact) return;
    try {
      await updateContactReminder(contact.id, reminderId, completed);
      await loadContact();
    } catch (error) {
      console.error("Erro ao atualizar lembrete:", error);
    }
  }

  function formatCurrency(cents: number) {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(cents / 100);
  }

  function formatDate(dateStr: string) {
    return new Date(dateStr).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function formatDateShort(dateStr: string) {
    return new Date(dateStr).toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }

  if (loading) {
    return (
      <div style={{ 
        padding: 48, 
        textAlign: "center",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "calc(100vh - 56px)",
      }}>
        <div className="spinner" style={{ width: 32, height: 32, marginBottom: 16 }} />
        <div style={{ color: "var(--text-muted)", fontSize: 14 }}>Carregando contato...</div>
      </div>
    );
  }

  if (!contact) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <h2 style={{ marginBottom: 8 }}>Contato não encontrado</h2>
        <p style={{ color: "var(--text-muted)", marginBottom: 24 }}>O contato solicitado não existe ou foi removido.</p>
        <Link to="/contacts" className="btn">
          ← Voltar para contatos
        </Link>
      </div>
    );
  }

  return (
    <div style={{ 
      minHeight: "calc(100vh - 56px)",
      background: "var(--bg)",
    }}>
      {/* Header moderno */}
      <div style={{
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
        boxShadow: "var(--shadow-sm)",
        padding: isMobile ? "20px 16px" : "24px 32px",
      }}>
        <div style={{
          maxWidth: 1400,
          margin: "0 auto",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 16,
          flexWrap: "wrap",
        }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <Link 
              to="/contacts" 
              style={{ 
                color: "var(--text-muted)", 
                textDecoration: "none",
                fontSize: 13,
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                marginBottom: 12,
              }}
            >
              ← Voltar para contatos
            </Link>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <div style={{
                width: 56,
                height: 56,
                borderRadius: "var(--radius-lg)",
                background: "var(--primary-soft)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 24,
                flexShrink: 0,
              }}>
                {contact.name ? contact.name.charAt(0).toUpperCase() : "?"}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <h1 style={{ 
                  margin: 0, 
                  fontSize: isMobile ? 24 : 28,
                  fontWeight: 700,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}>
                  {contact.name || "Sem nome"}
                </h1>
                <div style={{ 
                  display: "flex", 
                  flexWrap: "wrap", 
                  gap: 12, 
                  marginTop: 8,
                  fontSize: 13,
                  color: "var(--text-muted)",
                }}>
                  {contact.email && <span>{contact.email}</span>}
                  {contact.phone && <span>{contact.phone}</span>}
                  {contact.company && <span>{contact.company}</span>}
                </div>
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
            <Link 
              to={`/chat?thread=${contact.thread_id}`} 
              className="btn"
              style={{ fontSize: 14, padding: "10px 20px" }}
            >
              Ver conversa
            </Link>
          </div>
        </div>
      </div>

      {/* Conteúdo principal */}
      <div style={{
        maxWidth: 1400,
        margin: "0 auto",
        padding: isMobile ? "20px 16px" : "32px",
      }}>
        {/* Métricas principais */}
        <div style={{
          display: "grid",
          gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 16,
          marginBottom: 24,
        }}>
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
              Total de Pedidos
            </div>
            <div style={{ fontSize: 32, fontWeight: 700, color: "var(--primary-color)" }}>
              {contact.total_orders}
            </div>
          </div>
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
              Total Gasto
            </div>
            <div style={{ fontSize: 32, fontWeight: 700, color: "var(--success)" }}>
              {formatCurrency(contact.total_spent)}
            </div>
          </div>
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
              Ticket Médio
            </div>
            <div style={{ fontSize: 32, fontWeight: 700, color: "var(--text)" }}>
              {contact.average_ticket ? formatCurrency(contact.average_ticket) : "—"}
            </div>
          </div>
          {contact.last_interaction_at && (
            <div className="card" style={{ padding: 20 }}>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Última Interação
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text)" }}>
                {formatDateShort(contact.last_interaction_at)}
              </div>
            </div>
          )}
        </div>

        <div style={{
          display: "grid",
          gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr",
          gap: 24,
        }}>
          {/* Coluna Esquerda */}
          <div style={{ display: "grid", gap: 20 }}>
            {/* Dados Básicos */}
            <div className="card" style={{ padding: 24 }}>
              <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                Dados Básicos
              </h3>
              <div style={{ display: "grid", gap: 16 }}>
                {[
                  { key: "name", label: "Nome", type: "text" },
                  { key: "email", label: "Email", type: "email" },
                  { key: "phone", label: "Telefone", type: "tel" },
                  { key: "company", label: "Empresa", type: "text" },
                ].map(({ key, label, icon, type }) => {
                  const value = (contact as any)[key] || "";
                  const isEditing = editing === key;
                  return (
                    <div key={key}>
                      <label style={{ 
                        fontSize: 12, 
                        color: "var(--text-muted)", 
                        display: "block", 
                        marginBottom: 6,
                        fontWeight: 500,
                      }}>
                        {label}
                      </label>
                      {isEditing ? (
                        <div style={{ display: "flex", gap: 8 }}>
                          <input
                            type={type}
                            value={value}
                            onChange={(e) => setContact({ ...contact, [key]: e.target.value })}
                            onBlur={() => handleUpdate(key, value)}
                            onKeyPress={(e) => {
                              if (e.key === "Enter") {
                                handleUpdate(key, value);
                              }
                            }}
                            className="input"
                            style={{ flex: 1 }}
                            autoFocus
                          />
                          <button
                            className="btn ghost"
                            onClick={() => setEditing(null)}
                            style={{ padding: "8px 12px" }}
                          >
                            ✕
                          </button>
                        </div>
                      ) : (
                        <div 
                          onClick={() => setEditing(key)}
                          style={{ 
                            cursor: "pointer", 
                            padding: "10px 12px",
                            borderRadius: "var(--radius-md)",
                            background: "var(--panel)",
                            border: "1px solid transparent",
                            transition: "all var(--transition-base)",
                            minHeight: 40,
                            display: "flex",
                            alignItems: "center",
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.borderColor = "var(--border-light)";
                            e.currentTarget.style.background = "var(--bg)";
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.borderColor = "transparent";
                            e.currentTarget.style.background = "var(--panel)";
                          }}
                        >
                          {value || <span style={{ color: "var(--text-muted)" }}>—</span>}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Assinatura */}
            <div className="card" style={{ padding: 24 }}>
              <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                Assinatura
              </h3>
              {loadingSubscription ? (
                <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>
                  <div className="spinner" style={{ width: 20, height: 20, margin: "0 auto 12px" }} />
                  <div style={{ fontSize: 13 }}>Carregando...</div>
                </div>
              ) : subscriptionStatus?.has_subscription ? (
                <div style={{ display: "grid", gap: 16 }}>
                  <div style={{ 
                    display: "flex", 
                    justifyContent: "space-between", 
                    alignItems: "center",
                    padding: 16,
                    background: subscriptionStatus.is_active ? "var(--success-soft)" : "var(--danger-soft)",
                    borderRadius: "var(--radius-md)",
                  }}>
                    <span style={{ fontWeight: 600 }}>Status:</span>
                    <span className={`badge ${subscriptionStatus.is_active ? "badge-success" : "badge-danger"}`}>
                      {subscriptionStatus.is_active ? "Ativo" : "Inativo"}
                    </span>
                  </div>
                  {subscriptionStatus.product_title && (
                    <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 0" }}>
                      <span style={{ color: "var(--text-muted)" }}>Produto:</span>
                      <strong>{subscriptionStatus.product_title}</strong>
                    </div>
                  )}
                  {subscriptionStatus.expires_at && (
                    <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 0" }}>
                      <span style={{ color: "var(--text-muted)" }}>Expira em:</span>
                      <span>{formatDateShort(subscriptionStatus.expires_at)}</span>
                    </div>
                  )}
                  {subscriptions.length > 0 && (
                    <div style={{ marginTop: 8, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
                      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: "var(--text-muted)" }}>Histórico:</div>
                      <div style={{ display: "grid", gap: 8 }}>
                        {subscriptions.map((sub) => (
                          <div
                            key={sub.id}
                            style={{
                              padding: 12,
                              background: "var(--panel)",
                              borderRadius: "var(--radius-md)",
                              fontSize: 13,
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                              <span style={{ fontWeight: 500 }}>{sub.product_title || "Produto"}</span>
                              <span className={`badge ${sub.status === "active" ? "badge-success" : "badge-danger"}`} style={{ fontSize: 10 }}>
                                {sub.status === "active" ? "Ativo" : "Inativo"}
                              </span>
                            </div>
                            {sub.expires_at && (
                              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                                Expira: {formatDateShort(sub.expires_at)}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>
                  <div style={{ fontWeight: 500, marginBottom: 4 }}>Sem assinatura ativa</div>
                  <div style={{ fontSize: 12 }}>
                    Este contato ainda não tem uma assinatura na The Members
                  </div>
                </div>
              )}
            </div>

            {/* Vendas e Compras */}
            <div className="card" style={{ padding: 24 }}>
              <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                Vendas e Compras
              </h3>
              {loadingSales ? (
                <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>
                  <div className="spinner" style={{ width: 20, height: 20, margin: "0 auto 12px" }} />
                  <div style={{ fontSize: 13 }}>Carregando...</div>
                </div>
              ) : contactSales ? (
                <div style={{ display: "grid", gap: 20 }}>
                  <div style={{ 
                    display: "grid", 
                    gridTemplateColumns: isMobile ? "1fr" : "repeat(3, 1fr)", 
                    gap: 12 
                  }}>
                    <div style={{ padding: 16, background: "var(--panel)", borderRadius: "var(--radius-md)" }}>
                      <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                        Total de Vendas
                      </div>
                      <div style={{ fontSize: 24, fontWeight: 700 }}>{contactSales.total_sales}</div>
                    </div>
                    <div style={{ padding: 16, background: "var(--panel)", borderRadius: "var(--radius-md)" }}>
                      <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                        Faturamento
                      </div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: "var(--success)" }}>
                        {formatCurrency(contactSales.total_revenue)}
                      </div>
                    </div>
                    <div style={{ padding: 16, background: "var(--panel)", borderRadius: "var(--radius-md)" }}>
                      <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                        Assinaturas Ativas
                      </div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: "var(--success)" }}>
                        {contactSales.active_subscriptions}
                      </div>
                    </div>
                  </div>

                  {contactSales.sales.length > 0 && (
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Histórico de Vendas</div>
                      <div style={{ display: "grid", gap: 10 }}>
                        {contactSales.sales.map((sale) => (
                          <div
                            key={sale.id}
                            className="card"
                            style={{
                              padding: 16,
                              border: "1px solid var(--border)",
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                              <div style={{ flex: 1 }}>
                                <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>
                                  {sale.event === "sale.approved" ? "Venda Aprovada" : sale.event}
                                </div>
                                {sale.order_id && (
                                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                                    Pedido: #{sale.order_id}
                                  </div>
                                )}
                                {sale.source && (
                                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                                    Origem: {sale.source.charAt(0).toUpperCase() + sale.source.slice(1)}
                                  </div>
                                )}
                              </div>
                              {sale.value && (
                                <div style={{ fontSize: 18, fontWeight: 700, color: "var(--success)", marginLeft: 16 }}>
                                  {formatCurrency(sale.value)}
                                </div>
                              )}
                            </div>
                            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                              {formatDate(sale.created_at)}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {contactSales.sales.length === 0 && (
                    <div style={{ padding: 32, textAlign: "center", color: "var(--text-muted)" }}>
                      <div>Nenhuma venda registrada ainda.</div>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>⚠️</div>
                  <div>Erro ao carregar dados de vendas.</div>
                </div>
              )}
            </div>

            {/* Tags */}
            <div className="card" style={{ padding: 24 }}>
              <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                Tags
              </h3>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
                {contact.tags.length > 0 ? (
                  contact.tags.map((tag) => (
                    <span
                      key={tag.id}
                      className="chip"
                      style={{
                        background: "var(--primary-soft)",
                        color: "var(--primary-color)",
                        padding: "6px 12px",
                        fontSize: 12,
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      {tag.tag}
                      <button
                        onClick={() => handleRemoveTag(tag.id)}
                        style={{
                          background: "transparent",
                          border: "none",
                          color: "var(--primary-color)",
                          cursor: "pointer",
                          fontSize: 16,
                          padding: 0,
                          width: 18,
                          height: 18,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          borderRadius: "50%",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = "rgba(0,0,0,0.1)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = "transparent";
                        }}
                      >
                        ×
                      </button>
                    </span>
                  ))
                ) : (
                  <div style={{ fontSize: 13, color: "var(--text-muted)", fontStyle: "italic" }}>
                    Nenhuma tag adicionada
                  </div>
                )}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  type="text"
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                  onKeyPress={(e) => e.key === "Enter" && handleAddTag()}
                  placeholder="Adicionar tag..."
                  className="input"
                  style={{ flex: 1 }}
                />
                <button 
                  onClick={handleAddTag} 
                  className="btn" 
                  disabled={!newTag.trim()}
                  style={{ flexShrink: 0 }}
                >
                  Adicionar
                </button>
              </div>
            </div>
          </div>

          {/* Coluna Direita */}
          <div style={{ display: "grid", gap: 20 }}>
            {/* Notas */}
            <div className="card" style={{ padding: 24 }}>
              <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                Notas Internas
              </h3>
              {contact.notes.length > 0 ? (
                <div style={{ display: "grid", gap: 12, marginBottom: 16 }}>
                  {contact.notes.map((note) => (
                    <div
                      key={note.id}
                      className="card"
                      style={{
                        padding: 16,
                        background: "var(--panel)",
                        position: "relative",
                      }}
                    >
                      <div style={{ marginBottom: 8, fontSize: 14, lineHeight: 1.6 }}>
                        {note.content}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                        {formatDate(note.created_at)}
                      </div>
                      <button
                        onClick={() => handleDeleteNote(note.id)}
                        className="btn ghost"
                        style={{
                          position: "absolute",
                          top: 8,
                          right: 8,
                          padding: "4px 8px",
                          fontSize: 18,
                          minWidth: "auto",
                          width: 28,
                          height: 28,
                        }}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)", marginBottom: 16 }}>
                  <div style={{ fontSize: 13 }}>Nenhuma nota adicionada ainda</div>
                </div>
              )}
              <div style={{ display: "grid", gap: 8 }}>
                <textarea
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                  placeholder="Adicionar nota..."
                  className="input"
                  rows={3}
                  style={{ resize: "vertical" }}
                />
                <button 
                  onClick={handleAddNote} 
                  className="btn" 
                  disabled={!newNote.trim()}
                >
                  Adicionar Nota
                </button>
              </div>
            </div>

            {/* Lembretes */}
            <div className="card" style={{ padding: 24 }}>
              <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                Lembretes
              </h3>
              {contact.reminders.filter((r) => !r.completed).length > 0 ? (
                <div style={{ display: "grid", gap: 12, marginBottom: 16 }}>
                  {contact.reminders
                    .filter((r) => !r.completed)
                    .map((reminder) => (
                      <div
                        key={reminder.id}
                        className="card"
                        style={{
                          padding: 16,
                          background: "var(--warning-soft)",
                          border: "1px solid var(--warning)",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ marginBottom: 6, fontSize: 14, fontWeight: 500 }}>
                              {reminder.message}
                            </div>
                            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                              {formatDate(reminder.due_date)}
                            </div>
                          </div>
                          <button
                            onClick={() => handleToggleReminder(reminder.id, true)}
                            className="btn btn-sm"
                            style={{ flexShrink: 0 }}
                          >
                            Concluir
                          </button>
                        </div>
                      </div>
                    ))}
                </div>
              ) : (
                <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)", marginBottom: 16 }}>
                  <div style={{ fontSize: 13 }}>Nenhum lembrete pendente</div>
                </div>
              )}
              <div style={{ display: "grid", gap: 8 }}>
                <textarea
                  value={newReminder.message}
                  onChange={(e) => setNewReminder({ ...newReminder, message: e.target.value })}
                  placeholder="Mensagem do lembrete..."
                  className="input"
                  rows={2}
                  style={{ resize: "vertical" }}
                />
                <input
                  type="datetime-local"
                  value={newReminder.dueDate}
                  onChange={(e) => setNewReminder({ ...newReminder, dueDate: e.target.value })}
                  className="input"
                />
                <button
                  onClick={handleCreateReminder}
                  className="btn"
                  disabled={!newReminder.message.trim() || !newReminder.dueDate}
                >
                  Criar Lembrete
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

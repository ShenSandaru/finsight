import { describe, it, expect } from "vitest";
import { documentsApi } from "@/lib/api/documents";
import { searchApi } from "@/lib/api/search";
import { ragApi } from "@/lib/api/rag";
import { conversationsApi } from "@/lib/api/conversations";
import { reportsApi } from "@/lib/api/reports";
import { healthApi } from "@/lib/api/health";

describe("Domain Services Test Suite", () => {
  describe("Health API", () => {
    it("fetches backend health status", async () => {
      const res = await healthApi.check();
      expect(res.status).toBe("healthy");
      expect(res.app).toBe("FinSight");
    });
  });

  describe("Documents API", () => {
    it("lists uploaded documents", async () => {
      const res = await documentsApi.list();
      expect(res.total).toBe(2);
      expect(res.documents.length).toBe(2);
      expect(res.documents[0].filename).toBe("apple_10k_2025.pdf");
      expect(res.documents[0].status).toBe("indexed");
    });

    it("gets a single document by ID", async () => {
      const res = await documentsApi.get("11111111-1111-1111-1111-111111111111");
      expect(res.id).toBe("11111111-1111-1111-1111-111111111111");
      expect(res.total_pages).toBe(74);
      expect(res.total_chunks).toBe(142);
    });

    it("uploads a document with multipart FormData", async () => {
      const file = new File(["dummy pdf content"], "apple_10k.pdf", {
        type: "application/pdf",
      });
      const res = await documentsApi.upload({
        file,
        title: "Apple 10-K",
        source: "EDGAR",
      });
      expect(res.message).toBe("Document uploaded successfully");
      expect(res.document.status).toBe("processing");
    });

    it("deletes a document and receives null", async () => {
      const res = await documentsApi.delete("11111111-1111-1111-1111-111111111111");
      expect(res).toBeNull();
    });
  });

  describe("Search API", () => {
    it("searches chunks via semantic vector similarity", async () => {
      const res = await searchApi.search({
        query: "What was the total revenue in 2025?",
        top_k: 5,
        min_similarity: 0.5,
      });
      expect(res.total_results).toBe(1);
      expect(res.results[0].content).toContain("Total net sales were $412,000 million");
      expect(res.results[0].similarity).toBeGreaterThan(0.8);
    });
  });

  describe("RAG API", () => {
    it("executes single-turn grounded RAG query", async () => {
      const res = await ragApi.query({
        query: "What was Apple's revenue in 2025?",
        top_k: 5,
      });
      expect(res.answer).toContain("Apple reported total net sales of $412.0 billion");
      expect(res.grounded).toBe(true);
      expect(res.citations.length).toBe(1);
      expect(res.citations[0].statement_type).toBe("income_statement");
    });
  });

  describe("Conversations API", () => {
    it("creates a new conversation session", async () => {
      const res = await conversationsApi.createSession({
        title: "Apple FY2025 Margin Analysis",
      });
      expect(res.title).toBe("Apple FY2025 Margin Analysis");
      expect(res.message_count).toBe(2);
    });

    it("fetches session metadata", async () => {
      const res = await conversationsApi.getSession("44444444-4444-4444-4444-444444444444");
      expect(res.id).toBe("44444444-4444-4444-4444-444444444444");
    });

    it("fetches message history in chronological order", async () => {
      const res = await conversationsApi.getMessages("44444444-4444-4444-4444-444444444444");
      expect(res.length).toBe(2);
      expect(res[0].role).toBe("user");
      expect(res[1].role).toBe("assistant");
    });

    it("queries within a conversation session", async () => {
      const res = await conversationsApi.querySession(
        "44444444-4444-4444-4444-444444444444",
        {
          query: "What was Apple's gross margin in 2025?",
        }
      );
      expect(res.grounded).toBe(true);
      expect(res.answer).toContain("Apple's gross margin for FY2025 was 46.23%");
      expect(res.citations[0].chunk_type).toBe("table");
    });

    it("deletes a conversation session", async () => {
      const res = await conversationsApi.deleteSession("44444444-4444-4444-4444-444444444444");
      expect(res.message).toBe("Session deleted successfully");
    });
  });

  describe("Reports API", () => {
    it("creates an asynchronous report returning pending status", async () => {
      const res = await reportsApi.create({
        query: "Comprehensive financial report for Apple FY2025",
        title: "Apple FY2025 Report",
      });
      expect(res.status).toBe("pending");
    });

    it("fetches completed report details and findings", async () => {
      const res = await reportsApi.get("66666666-6666-6666-6666-666666666666");
      expect(res.id).toBe("66666666-6666-6666-6666-666666666666");
      expect(res.status).toBe("completed");
      expect(res.executive_summary).toBeDefined();
      expect(res.findings?.length).toBe(1);
    });

    it("lists reports with pagination", async () => {
      const res = await reportsApi.list();
      expect(res.total).toBe(1);
      expect(res.reports.length).toBe(1);
    });

    it("deletes a report record", async () => {
      const res = await reportsApi.delete("66666666-6666-6666-6666-666666666666");
      expect(res).toBeNull();
    });
  });
});

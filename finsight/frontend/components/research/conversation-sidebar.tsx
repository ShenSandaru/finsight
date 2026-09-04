"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { MessageSquare, Trash2, Plus, Loader2, AlertTriangle } from "lucide-react";
import type { ConversationSessionResponse } from "@/types/api";

interface ConversationSidebarProps {
  conversations: ConversationSessionResponse[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onCreateSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  isCreating: boolean;
  isDeleting: boolean;
}

export function ConversationSidebar({
  conversations,
  activeSessionId,
  onSelectSession,
  onCreateSession,
  onDeleteSession,
  isCreating,
  isDeleting,
}: ConversationSidebarProps) {
  const [sessionToDelete, setSessionToDelete] = useState<ConversationSessionResponse | null>(
    null
  );

  const handleDeleteConfirm = () => {
    if (sessionToDelete) {
      onDeleteSession(sessionToDelete.id);
      setSessionToDelete(null);
    }
  };

  const formatDate = (isoString?: string) => {
    if (!isoString) return "";
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    } catch {
      return "";
    }
  };

  return (
    <>
      <div
        className="w-full sm:w-64 border-r bg-muted/10 flex flex-col h-full overflow-hidden"
        data-testid="conversation-sidebar"
      >
        {/* Header / New Research Button */}
        <div className="p-3 border-b">
          <Button
            size="sm"
            onClick={onCreateSession}
            disabled={isCreating}
            className="w-full gap-2 text-xs h-8 justify-center"
            data-testid="new-research-btn"
          >
            {isCreating ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Plus className="h-3.5 w-3.5" />
            )}
            <span>New Research</span>
          </Button>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {conversations.length === 0 ? (
            <div className="p-4 text-center space-y-1.5">
              <MessageSquare className="h-5 w-5 mx-auto text-muted-foreground/60" />
              <p className="text-xs font-medium text-muted-foreground">
                No active research
              </p>
              <p className="text-[11px] text-muted-foreground/80">
                Create a session to begin conversational filing audits.
              </p>
            </div>
          ) : (
            conversations.map((session) => {
              const isActive = session.id === activeSessionId;
              const displayTitle = session.title || "Untitled Research";

              return (
                <div
                  key={session.id}
                  className={`group flex items-center justify-between rounded-md px-2.5 py-2 text-xs transition-colors cursor-pointer ${
                    isActive
                      ? "bg-primary text-primary-foreground font-medium"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                  onClick={() => onSelectSession(session.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      onSelectSession(session.id);
                    }
                  }}
                  data-testid={`session-item-${session.id}`}
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1 pr-1">
                    <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-left">{displayTitle}</p>
                      <span
                        className={`text-[10px] font-mono ${
                          isActive
                            ? "text-primary-foreground/75"
                            : "text-muted-foreground/70"
                        }`}
                      >
                        {formatDate(session.created_at)} • {session.message_count} msgs
                      </span>
                    </div>
                  </div>

                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSessionToDelete(session);
                    }}
                    className={`h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity ${
                      isActive
                        ? "text-primary-foreground hover:bg-primary-foreground/20 hover:text-primary-foreground"
                        : "text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                    }`}
                    aria-label={`Delete conversation ${displayTitle}`}
                    data-testid={`delete-session-btn-${session.id}`}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={Boolean(sessionToDelete)}
        onOpenChange={(open) => !open && setSessionToDelete(null)}
      >
        <DialogContent className="sm:max-w-[420px]" data-testid="delete-session-dialog">
          <DialogHeader className="gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-destructive/10 text-destructive">
              <AlertTriangle className="h-4 w-4" />
            </div>
            <DialogTitle className="text-base font-semibold">
              Delete Research Session?
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground leading-relaxed">
              Are you sure you want to delete{" "}
              <span className="font-semibold text-foreground">
                {sessionToDelete?.title || "this research session"}
              </span>
              ? This will permanently erase the message history from conversational memory.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 pt-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setSessionToDelete(null)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
              className="gap-1.5"
              data-testid="confirm-delete-session-btn"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Deleting...</span>
                </>
              ) : (
                <span>Delete Session</span>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Loader2, Save } from 'lucide-react';
import RichTextEditor from './RichTextEditor';
import api from '../services/api';

interface NotesEditorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sessionId: string;
  initialNotes: string;
  onNotesSaved: (notes: string) => void;
}

const NotesEditorDialog: React.FC<NotesEditorDialogProps> = ({
  open,
  onOpenChange,
  sessionId,
  initialNotes,
  onNotesSaved,
}) => {
  const [notes, setNotes] = useState<string>(initialNotes);
  const [saving, setSaving] = useState(false);

  // Update local notes when initialNotes changes or dialog opens
  useEffect(() => {
    if (open) {
      setNotes(initialNotes);
    }
  }, [open, initialNotes]);

  const handleSave = async () => {
    try {
      setSaving(true);
      await api.put(`/papi-measurements/session/${sessionId}/notes`, { notes });
      onNotesSaved(notes);
      onOpenChange(false);
    } catch (err: any) {
      console.error('Error saving notes:', err);
      alert(err.response?.data?.detail || 'Failed to save notes');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setNotes(initialNotes); // Reset to original notes
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Edit Measurement Notes</DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-auto py-4">
          <RichTextEditor
            content={notes}
            onChange={setNotes}
            editable={true}
          />
        </div>

        <DialogFooter>
          <Button onClick={handleCancel} variant="outline" disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving} className="bg-blue-600 hover:bg-blue-700">
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save Notes
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default NotesEditorDialog;

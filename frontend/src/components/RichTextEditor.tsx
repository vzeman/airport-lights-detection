import React from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Underline from '@tiptap/extension-underline';
import { Markdown } from 'tiptap-markdown';
import { Button } from './ui/button';
import './RichTextEditor.css';
import {
  Bold,
  Italic,
  Underline as UnderlineIcon,
  List,
  ListOrdered,
  Heading1,
  Heading2,
  Heading3,
  Quote,
  Code,
  Undo,
  Redo,
  LinkIcon,
} from 'lucide-react';

interface RichTextEditorProps {
  content: string;
  onChange: (markdown: string) => void;
  editable?: boolean;
}

const RichTextEditor: React.FC<RichTextEditorProps> = ({
  content,
  onChange,
  editable = true,
}) => {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3],
        },
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: 'text-blue-600 underline cursor-pointer',
        },
      }),
      Underline,
      Markdown.configure({
        html: true, // Allow HTML tags in markdown
        tightLists: true, // Use tight lists
        transformPastedText: true, // Transform pasted markdown
        transformCopiedText: true, // Transform copied markdown
      }),
    ],
    content: content || '',
    editable: editable,
    onUpdate: ({ editor }) => {
      // The Markdown extension automatically handles conversion
      // We can get the markdown using the editor's storage
      // @ts-ignore - tiptap-markdown adds this to storage
      const markdown = editor.storage.markdown.getMarkdown();
      onChange(markdown);
    },
    editorProps: {
      attributes: {
        class: editable
          ? 'focus:outline-none min-h-[400px] p-4'
          : 'p-4',
      },
      handleKeyDown: (view, event) => {
        // Prevent keyboard shortcuts from bubbling to the page
        if (editable) {
          const modKey = event.metaKey || event.ctrlKey;
          const isShortcut = modKey && (
            event.key === 'b' || // Bold
            event.key === 'i' || // Italic
            event.key === 'u' || // Underline
            event.key === 'z' || // Undo
            event.key === 'y' || // Redo
            event.key === 'k' || // Link
            event.key === '1' || event.key === '2' || event.key === '3' || // Headings
            event.shiftKey // Any shift combinations
          );

          if (isShortcut) {
            event.stopPropagation();
          }
        }
        return false; // Let TipTap handle the event
      },
    },
  });

  const setLink = () => {
    if (!editor) return;

    const previousUrl = editor.getAttributes('link').href;
    const url = window.prompt('Enter URL:', previousUrl);

    if (url === null) return;

    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }

    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
  };

  if (!editor) {
    return null;
  }

  const handleContainerKeyDown = (e: React.KeyboardEvent) => {
    // Prevent all keyboard shortcuts in the editor from affecting the page
    if (editable) {
      const modKey = e.metaKey || e.ctrlKey;
      if (modKey) {
        e.stopPropagation();
      }
    }
  };

  return (
    <div
      className={editable ? "border rounded-lg overflow-hidden" : ""}
      onKeyDown={handleContainerKeyDown}
    >
      {editable && (
        <div className="flex flex-wrap gap-1 p-2 border-b bg-gray-50">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={editor.isActive('bold') ? 'bg-gray-200' : ''}
          >
            <Bold className="w-4 h-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={editor.isActive('italic') ? 'bg-gray-200' : ''}
          >
            <Italic className="w-4 h-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleUnderline().run()}
            className={editor.isActive('underline') ? 'bg-gray-200' : ''}
          >
            <UnderlineIcon className="w-4 h-4" />
          </Button>

          <div className="w-px h-6 bg-gray-300 mx-1" />

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
            className={editor.isActive('heading', { level: 1 }) ? 'bg-gray-200' : ''}
          >
            <Heading1 className="w-4 h-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            className={editor.isActive('heading', { level: 2 }) ? 'bg-gray-200' : ''}
          >
            <Heading2 className="w-4 h-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
            className={editor.isActive('heading', { level: 3 }) ? 'bg-gray-200' : ''}
          >
            <Heading3 className="w-4 h-4" />
          </Button>

          <div className="w-px h-6 bg-gray-300 mx-1" />

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            className={editor.isActive('bulletList') ? 'bg-gray-200' : ''}
          >
            <List className="w-4 h-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            className={editor.isActive('orderedList') ? 'bg-gray-200' : ''}
          >
            <ListOrdered className="w-4 h-4" />
          </Button>

          <div className="w-px h-6 bg-gray-300 mx-1" />

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
            className={editor.isActive('blockquote') ? 'bg-gray-200' : ''}
          >
            <Quote className="w-4 h-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleCodeBlock().run()}
            className={editor.isActive('codeBlock') ? 'bg-gray-200' : ''}
          >
            <Code className="w-4 h-4" />
          </Button>

          <div className="w-px h-6 bg-gray-300 mx-1" />

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={setLink}
            className={editor.isActive('link') ? 'bg-gray-200' : ''}
          >
            <LinkIcon className="w-4 h-4" />
          </Button>

          <div className="w-px h-6 bg-gray-300 mx-1" />

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().undo().run()}
            disabled={!editor.can().undo()}
          >
            <Undo className="w-4 h-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().redo().run()}
            disabled={!editor.can().redo()}
          >
            <Redo className="w-4 h-4" />
          </Button>
        </div>
      )}
      <EditorContent editor={editor} />
    </div>
  );
};

export default RichTextEditor;

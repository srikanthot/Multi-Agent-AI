"use client";
 
import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { arrayBufferToBase64 } from '@/lib/utils';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import './pdfviewer.css'
 
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
 
interface TextItemProps {
  str: string;
  itemIndex: number
}
 
interface PdfViewerProps {
  src: string;
  initialPage?: number;
  highlightWords?: string[];
  scale?: number;
  onClose: () => void;
}
 
function PdfViewer({ src, initialPage = 1, highlightWords = [], scale = 1.5, onClose }: PdfViewerProps) {
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pdfData, setPdfData] = useState<ArrayBuffer | null>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [size, setSize] = useState<{ width: number, height: number } | null>(null);
  const [isResizing, setIsResizing] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0, posX: 0, posY: 0 });
  const resizeStartRef = useRef({ x: 0, y: 0, width: 0, height: 0, direction: "" });
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const viewerRef = useRef<HTMLDivElement>(null);
 
  // Caches the pdf so it doesn't refetch on onload.  Convert to Base64 string to avoid page number error
  // associated with react-pdf
  const memoPdfData = useMemo(() => {
    let base64String;
    if (pdfData) {
      base64String = arrayBufferToBase64(pdfData);
    }
    return base64String ? `data:application/pdf;base64,${base64String}` : null;
  }, [pdfData])
 
  // Load PDF data
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setPdfData(null);
 
    fetch(src)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.arrayBuffer();
      })
      .then((data) => {
        if (!cancelled) setPdfData(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(`Failed to fetch PDF: ${err.message}`);
          setLoading(false);
        }
      })
  }, [src]);
 
  // Focus close button on mount, lock body scroll, and close on Escape
  useEffect(() => {
    closeButtonRef.current?.focus();
 
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
 
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
 
    return () => {
      document.body.style.overflow = originalOverflow;
      document.removeEventListener("keydown", handler);
    }
  }, [onClose]);
 
  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setTotalPages(numPages);
    setLoading(false);
    setError(null);
  }
 
  const onDocumentLoadError = () => {
    setError('Failed to load PDF');
    setLoading(false);
  }
 
  const goToPage = (pageNum: number) => {
    if (pageNum >= 1 && pageNum <= totalPages) {
      setCurrentPage(pageNum);
    }
  };
 
  const prevPage = () => goToPage(currentPage - 1);
  const nextPage = () => goToPage(currentPage + 1);
 
  // Text rendering for highlighting
  const textRenderer = useCallback(
    ({ str }: TextItemProps) => {
      if (highlightWords.length === 0) return str;
 
      const lowerStr = str.toLowerCase();
      const shouldHighlight = highlightWords.some(
        (word) => lowerStr.includes(word.toLowerCase())
      );
 
      if (shouldHighlight) {
        let result = str;
        highlightWords.forEach((word) => {
          const regex = new RegExp(`(${word})`, 'gi');
          result = result.replace(regex, '<mark class="pdf-highlight">$1</mark>');
        });
        return result;
      }
 
      return str;
    }, [highlightWords]
  );
 
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };
 
  const handleDragStart = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest("button, input")) return; //ignore drag if clicking
 
    setIsDragging(true);
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      posX: position.x,
      posY: position.y
    };
 
    const handleMouseMove = (moveEvent: MouseEvent) => {
      const deltaX = moveEvent.clientX - dragStartRef.current.x;
      const deltaY = moveEvent.clientY - dragStartRef.current.y;
      setPosition({
        x: dragStartRef.current.posX + deltaX,
        y: dragStartRef.current.posY + deltaY
      });
    };
 
    const handleMouseUp = () => {
      setIsDragging(false);
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
 
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  };
 
  const handleResizeStart = (e: React.MouseEvent, direction: string) => {
    e.preventDefault();
    e.stopPropagation();
 
    const viewer = viewerRef.current;
    if (!viewer) return;
 
    const rect = viewer.getBoundingClientRect();
    setIsResizing(true);
    resizeStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      width: rect.width,
      height: rect.height,
      direction
    };
 
    const handleMouseMove = (moveEvent: MouseEvent) => {
      const { direction, x, y, width, height } = resizeStartRef.current;
      const deltaX = moveEvent.clientX - x;
      const deltaY = moveEvent.clientY - y;
 
      let newWidth = width;
      let newHeight = height;
 
      if (direction.includes("e")) newWidth = Math.max(300, width + deltaX);
      if (direction.includes("w")) newWidth = Math.max(300, width - deltaX);
      if (direction.includes("s")) newHeight = Math.max(200, height + deltaY);
      if (direction.includes("n")) newHeight = Math.max(200, height - deltaY);
 
      setSize({ width: newWidth, height: newHeight });
 
      // Adjust position for north/west resizing
      if (direction.includes("w")) {
        setPosition((pos) => ({
          ...pos,
          x: position.x + (width - newWidth)
        }));
        resizeStartRef.current.width = newWidth;
        resizeStartRef.current.x = moveEvent.clientX;
      }
      if (direction.includes("n")) {
        setPosition((pos) => ({
          ...pos,
          y: pos.y + (height - newHeight)
        }));
        resizeStartRef.current.height = newHeight;
        resizeStartRef.current.y = moveEvent.clientY;
      }
    };
 
    const handleMouseUp = () => {
      setIsResizing(false);
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
 
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  }
 
  const handleResetPosition = () => {
    setPosition({ x: 0, y: 0 });
    setSize(null);
  };
 
  if (error) {
    return (
      <div className="pdf-viewer overlay"
        role="dialog"
        aria-modal="true"
        aria-label="PDF viewer error"
        onClick={handleOverlayClick}>
        <div className='pdf-viewer-error'>
          {error}
        </div>
      </div>
    );
  }
 
  return (
    <div className="pdf-viewer-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="PDF viewer error"
    >
      <div
        ref={viewerRef}
        className={`pdf-viewer ${isDragging ? "is-dragging" : ""} ${isResizing ? "is-resizing" : ""}`}
        style={{
          transform: `translate(${position.x}px, ${position.y}px)`,
          ...(size && { width: size.width, height: size.height })
        }}
      >
        <div className="pdf-resize-handle pdf-resize-n" onMouseDown={(e) => handleResizeStart(e, "n")} />
        <div className="pdf-resize-handle pdf-resize-s" onMouseDown={(e) => handleResizeStart(e, "s")} />
        <div className="pdf-resize-handle pdf-resize-e" onMouseDown={(e) => handleResizeStart(e, "e")} />
        <div className="pdf-resize-handle pdf-resize-w" onMouseDown={(e) => handleResizeStart(e, "w")} />
        <div className="pdf-resize-handle pdf-resize-ne" onMouseDown={(e) => handleResizeStart(e, "ne")} />
        <div className="pdf-resize-handle pdf-resize-nw" onMouseDown={(e) => handleResizeStart(e, "nw")} />
        <div className="pdf-resize-handle pdf-resize-se" onMouseDown={(e) => handleResizeStart(e, "se")} />
        <div className="pdf-resize-handle pdf-resize-sw" onMouseDown={(e) => handleResizeStart(e, "sw")} />
        <button
          ref={closeButtonRef}
          className="pdf-close-button"
          onClick={onClose}
          aria-label="Close PDF viewer (Escape)"
          type="button">
          &times;
          </button>
        {(position.x !== 0 || position.y !== 0 || size !== null) && (
          <button
            className="pdf-reset-position-button"
            onClick={handleResetPosition}
            aria-label="Reset viewer position and size"
            type="button">
            Reset
          </button>
        )}
 
        <div className="pdf-toolbar"
          role="toolbar"
          aria-label="PDF navigation - drag to move"
          onMouseDown={handleDragStart}>
          <button
            onClick={prevPage}
            disabled={currentPage <= 1}
            aria-label="Previous page">
            Previous
                </button>
          <span className="pdf-page-info">
            <label>
              <span className="visually-hidden">Current page</span>
              <input
                type="number"
                value={currentPage}
                onChange={(e) => goToPage(Number(e.target.value))}
                min={1}
                max={totalPages}
                aria-label={`Page ${currentPage} of ${totalPages || "unknown"}`}
              />
            </label>
            <span aria-hidden="true">/ {totalPages || '...'} </span>
          </span>
 
          <button onClick={nextPage}
            disabled={currentPage >= totalPages || loading}
            aria-label="Next page">
            Next
          </button>
        </div>
 
        <div className="pdf-container">
          {loading && <div className='pdf-viewer-loading'
            role="status"
            aria-live="polite"
          >Loading PDF...</div>}
          <Document
            file={memoPdfData}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading=""
            noData=""
          >
            <Page
              pageNumber={currentPage ? currentPage : 1}
              scale={scale}
              renderTextLayer={true}
              renderAnnotationLayer={true}
              customTextRenderer={highlightWords.length > 0 ? textRenderer : undefined}
            />
          </Document>
        </div>
      </div >
    </div>
  );
}
 
export default PdfViewer;
 
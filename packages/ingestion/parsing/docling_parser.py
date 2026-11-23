
import tempfile
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import PdfFormatOption

from packages.ingestion.parsing.schemas import (
    BoundingBox,
    DocumentElement,
    ParsedDocument,
)
from packages.storage.s3_client import S3Client


class DocumentParsingError(Exception):
    pass


class DoclingParser:

    def __init__(self):
        pdf_options = PdfPipelineOptions()
        pdf_options.do_ocr = True
        pdf_options.do_table_structure = True
        pdf_options.document_timeout = 120

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pdf_options
                )
            }
        )

    def parse(
        self,
        file_path: str | Path,
        filename: str,
    ) -> ParsedDocument:

        try:
            result = self.converter.convert(str(file_path))
            document = result.document

            if document is None:
                raise DocumentParsingError(
                    "Docling returned no document"
                )

            elements = []
            heading_stack = []

            for index, (item, level) in enumerate(
                document.iterate_items(traverse_pictures=True)
            ):

                label = getattr(item.label, "value", str(item.label))

                # Extract table content as Markdown.
                if label == "table":
                    try:
                        dataframe = item.export_to_dataframe(
                            doc=document
                        )
                        text = dataframe.to_markdown(index=False)
                    except Exception:
                        text = ""

                else:
                    text = getattr(item, "text", "") or ""

                text = text.strip()

                if not text:
                    continue

                # Maintain heading hierarchy.
                if label == "section_header":
                    heading_level = max(
                        1,
                        int(getattr(item, "level", 1)),
                    )

                    heading_stack = heading_stack[
                        :heading_level - 1
                    ]
                    heading_stack.append(text)

                provenance = (
                    item.prov[0] if getattr(item, "prov", None) else None
                )

                page_number = (
                    provenance.page_no if provenance else None
                )

                bbox = None

                if provenance and provenance.bbox:
                    box = provenance.bbox
                    bbox = BoundingBox(
                        left=box.l,
                        top=box.t,
                        right=box.r,
                        bottom=box.b,
                    )

                elements.append(
                    DocumentElement(
                        element_id=f"element-{index:06d}",
                        element_type=label,
                        text=text,
                        page_number=page_number,
                        bbox=bbox,
                        heading_path=heading_stack.copy(),
                        metadata={
                            "docling_level": level,
                            "docling_ref": getattr(
                                item, "self_ref", None
                            ),
                        },
                    )
                )

            full_text = "\n\n".join(
                element.text for element in elements
            )

            page_count = len(document.pages)

            # Flag documents whose extracted text is suspiciously low.
            chars_per_page = (
                len(full_text) / page_count
                if page_count else 0
            )

            return ParsedDocument(
                filename=filename,
                page_count=page_count,
                elements=elements,
                full_text=full_text,
                markdown=document.export_to_markdown(),
                total_characters=len(full_text),
                needs_ocr_review=(
                    page_count > 0 and chars_per_page < 100
                ),
            )

        except DocumentParsingError:
            raise

        except Exception as exc:
            raise DocumentParsingError(
                f"Docling parsing failed: {exc}"
            ) from exc


def parse_rustfs_object(
    storage: S3Client,
    storage_key: str,
    filename: str,
) -> ParsedDocument:

    response = storage.get_object(storage_key)

    try:
        with tempfile.NamedTemporaryFile(
            suffix=Path(filename).suffix,
            delete=True,
        ) as temp_file:

            body = response["Body"]

            try:
                for chunk in body.iter_chunks(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        temp_file.write(chunk)
            finally:
                body.close()

            temp_file.flush()

            parser = DoclingParser()

            return parser.parse(
                file_path=temp_file.name,
                filename=filename,
            )

    finally:
        response["Body"].close()

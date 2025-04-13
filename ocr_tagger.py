import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
from PIL import Image, ImageTk
from paddleocr import PaddleOCR
import json
import os

ocr = PaddleOCR(use_angle_cls=True, lang='japan')  # 日本語対応

class BIFTagger:
    TAGS_FILE = "tags.json"

    def __init__(self, root):
        self.root = root
        self.root.title("OCR BIFタグ付けツール")
        self.selected_tag = "O"
        self.image_path = None
        self.scale = 1.0  # 画像のスケールを管理

        self.tag_colors = {
            "O": "gray",
            "name": "blue",
            "address": "green",
            "title": "orange"
        }

        self.load_tags()  # タグ情報を初期化時に読み込む

        self.text_boxes = []  # OCRで検出された文字情報
        self.undo_stack = []

        # 画像表示エリア用のフレームを作成
        self.image_frame = tk.Frame(root)
        self.image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.image_frame, width=800, height=600, bg='white', scrollregion=(0, 0, 1000, 1000))
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.scroll_x = tk.Scrollbar(self.image_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.scroll_x.grid(row=1, column=0, sticky="ew")
        self.scroll_y = tk.Scrollbar(self.image_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scroll_y.grid(row=0, column=1, sticky="ns")

        self.image_frame.grid_rowconfigure(0, weight=1)
        self.image_frame.grid_columnconfigure(0, weight=1)

        self.canvas.configure(xscrollcommand=self.scroll_x.set, yscrollcommand=self.scroll_y.set)

        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack()

        # 基本ボタン
        tk.Button(self.btn_frame, text="画像を開く", command=self.load_image).pack(side=tk.LEFT)
        tk.Button(self.btn_frame, text="保存", command=self.save_tags).pack(side=tk.LEFT)
        tk.Button(self.btn_frame, text="読み込み", command=self.load_saved_data).pack(side=tk.LEFT)
        tk.Button(self.btn_frame, text="Undo", command=self.undo).pack(side=tk.LEFT)
        tk.Button(self.btn_frame, text="タグ編集", command=self.edit_tags).pack(side=tk.LEFT)
        tk.Button(self.btn_frame, text="フィット表示", command=self.fit_to_canvas).pack(side=tk.LEFT)
        tk.Button(self.btn_frame, text="タグ情報表示", command=self.show_tag_table).pack(side=tk.LEFT)

        self.selected_tag_label = tk.Label(self.btn_frame, text=f"選択中のタグ: {self.selected_tag}", fg="black")
        self.selected_tag_label.pack(side=tk.LEFT)

        # タグ選択ボタン
        self.tag_button_frame = tk.Frame(root)
        self.tag_button_frame.pack()
        self.update_tag_buttons()

        self.table_frame = tk.Frame(root)
        self.table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)  # エリアのサイズを大きくするためにパディングを追加

        self.table_canvas = tk.Canvas(self.table_frame)
        self.table_scrollbar = tk.Scrollbar(self.table_frame, orient=tk.VERTICAL, command=self.table_canvas.yview)
        self.table_inner_frame = tk.Frame(self.table_canvas)

        self.table_inner_frame.bind(
            "<Configure>",
            lambda e: self.table_canvas.configure(scrollregion=self.table_canvas.bbox("all"))
        )

        self.table_canvas.create_window((0, 0), window=self.table_inner_frame, anchor="nw")
        self.table_canvas.configure(yscrollcommand=self.table_scrollbar.set)

        self.table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.table_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.update_tag_table()  # 初期状態で表を更新

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<MouseWheel>", self.zoom_image)  # マウスホイールイベントをバインド

    def update_tag_buttons(self):
        for widget in self.tag_button_frame.winfo_children():
            widget.destroy()
        for tag in self.tag_colors:
            tk.Button(self.tag_button_frame, text=tag, bg=self.tag_colors[tag], fg="white",
                      command=lambda t=tag: self.select_tag(t)).pack(side=tk.LEFT)

    def select_tag(self, tag):
        self.selected_tag = tag
        self.selected_tag_label.config(text=f"選択中のタグ: {self.selected_tag}")
        print("選択タグ：", tag)

    def load_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
        if not path:
            return
        self.image_path = path
        image = Image.open(path)
        self.tk_image = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        self.scale = 1.0  # 画像を読み込むたびにスケールをリセット

        # OCR実行
        result = ocr.ocr(path, cls=True)
        self.text_boxes.clear()

        for line in result[0]:
            box, (text, score) = line  # スコアも取得
            x1 = min(point[0] for point in box)  # x座標の最小値
            y1 = min(point[1] for point in box)  # y座標の最小値
            x2 = max(point[0] for point in box)  # x座標の最大値
            y2 = max(point[1] for point in box)  # y座標の最大値
            tag = "O"
            color = self.tag_colors.get(tag, "gray")
            rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2, tags="box")
            text_id = self.canvas.create_text(x1, y1 - 3, text=text, anchor=tk.SW, fill=color, font=("Arial", 10, "bold"))
            tag_id = self.canvas.create_text(x2, y2 + 3, text=tag, anchor=tk.NE, fill=color, font=("Arial", 10, "bold"))
            self.text_boxes.append({
                "text": text,
                "box": [[x1, y1], [x2, y2]],
                "tag": tag,
                "score": score,  # スコアを保存
                "rect_id": rect_id,
                "text_id": text_id,
                "tag_id": tag_id
            })

        # OCRで検出された矩形を再描画
        for item in self.text_boxes:
            box = item["box"]
            x, y = box[0]  # 左上の座標
            x2, y2 = box[1]  # 右下の座標
            width = x2 - x
            height = y2 - y
            scaled_box = [
                x * self.scale,
                y * self.scale,
                width * self.scale,
                height * self.scale
            ]
            color = self.tag_colors.get(item["tag"], "gray")
            rect_id = self.canvas.create_rectangle(
                scaled_box[0], scaled_box[1],
                scaled_box[0] + scaled_box[2], scaled_box[1] + scaled_box[3],
                outline=color, width=2, tags="box"
            )
            text_id = self.canvas.create_text(
                scaled_box[0], scaled_box[1] - 3,
                text=item["text"], anchor=tk.SW, fill=color, font=("Arial", 10, "bold")
            )
            tag_id = self.canvas.create_text(
                scaled_box[0] + scaled_box[2], scaled_box[1] + scaled_box[3] + 3,
                text=item["tag"], anchor=tk.NE, fill=color, font=("Arial", 10, "bold")
            )
            item.update({"rect_id": rect_id, "text_id": text_id, "tag_id": tag_id})

        self.update_tag_table()  # 画像を開いた後に表を更新

    def on_click(self, event):
        # スクロールオフセットを考慮してクリック位置を計算
        x = (self.canvas.canvasx(event.x)) / self.scale
        y = (self.canvas.canvasy(event.y)) / self.scale
        for item in self.text_boxes:
            box = item["box"]
            x1, y1 = box[0]  # 左上の座標
            x2, y2 = box[1]  # 右下の座標

            if x1 <= x <= x2 and y1 <= y <= y2:  # クリック位置が矩形内にあるか確認
                item["tag"] = self.selected_tag
                color = self.tag_colors.get(self.selected_tag, "red")
                self.canvas.itemconfig(item["rect_id"], outline=color)
                self.canvas.itemconfig(item["tag_id"], text=self.selected_tag, fill=color)
                self.canvas.itemconfig(item["text_id"], fill=color)
                self.undo_stack.append(item.copy())
                self.update_tag_table()  # タグ変更後に表を更新
                print(f"{item['text']} にタグ '{self.selected_tag}' を付与")
                break

    def undo(self):
        if not self.undo_stack:
            return
        last = self.undo_stack.pop()
        for item in self.text_boxes:
            if item["rect_id"] == last["rect_id"]:
                item["tag"] = "O"
                self.canvas.itemconfig(item["rect_id"], outline=self.tag_colors["O"])
                if "text_id" in item:
                    self.canvas.delete(item["text_id"])
                item["text_id"] = self.canvas.create_text(
                    item["box"][2][0], item["box"][2][1],
                    text="O", anchor=tk.SE, fill=self.tag_colors["O"], font=("Arial", 10, "bold"))
                break

    def save_tags(self):
        data = {
            "image_path": self.image_path,
            "scale": self.scale,  # スケール情報を保存
            "items": []
        }
        for item in self.text_boxes:
            box = item["box"]
            x1, y1 = box[0]  # 左上の座標
            x2, y2 = box[1]  # 右下の座標
            if x1 > x2 or y1 > y2:  # 座標が逆転している場合を修正
                x1, x2 = min(x1, x2), max(x1, x2)
                y1, y2 = min(y1, y2), max(y1, y2)
            data["items"].append({
                "text": item["text"],
                "box": [[x1, y1], [x2, y2]],  # 左上と右下の形式に修正
                "tag": item["tag"],
                "score": item["score"]  # スコアを保存
            })
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("保存完了", f"{path} に保存しました。")

    def load_saved_data(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return

        with open(path, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        self.text_boxes.clear()
        self.canvas.delete("all")  # キャンバスをリセット
        self.canvas.xview_moveto(0)  # 水平方向のスクロール位置をリセット
        self.canvas.yview_moveto(0)  # 垂直方向のスクロール位置をリセット
        self.scale = 1.0  # ズームをリセット

        img_path = saved_data.get("image_path")
        if img_path and os.path.exists(img_path):
            image = Image.open(img_path)
            self.tk_image = ImageTk.PhotoImage(image)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
            self.image_path = img_path
        else:
            messagebox.showwarning("画像ファイルが見つかりません", "保存された画像ファイルが見つかりませんでした。")

        self.canvas.xview_moveto(0)  # 水平方向のスクロール位置をリセット
        self.canvas.yview_moveto(0)  # 垂直方向のスクロール位置をリセット
        self.scale = 1.0  # ズームをリセット

        self.scale = saved_data.get("scale", 1.0)  # スケール情報を読み込む

        # 画像を再描画
        image = Image.open(self.image_path)
        new_size = (int(image.width * self.scale), int(image.height * self.scale))
        resized_image = image.resize(new_size, Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized_image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        for item in saved_data["items"]:
            box = item["box"]
            x1, y1 = box[0]  # 左上の座標
            x2, y2 = box[1]  # 右下の座標
            color = self.tag_colors.get(item["tag"], "gray")

            rect_id = self.canvas.create_rectangle(
                x1 * self.scale, y1 * self.scale,
                x2 * self.scale, y2 * self.scale,
                outline=color, width=2, tags="box"
            )
            text_id = self.canvas.create_text(
                x1 * self.scale, y1 * self.scale - 3,
                text=item["text"], anchor=tk.SW, fill=color, font=("Arial", 10, "bold")
            )
            tag_id = self.canvas.create_text(
                x2 * self.scale, y2 * self.scale + 3,
                text=item["tag"], anchor=tk.NE, fill=color, font=("Arial", 10, "bold")
            )

            self.text_boxes.append({
                "text": item["text"],
                "box": [[x1, y1], [x2, y2]],
                "tag": item["tag"],
                "score": item.get("score", 0.0),  # スコアを読み込む。デフォルトは0.0
                "rect_id": rect_id,
                "text_id": text_id,
                "tag_id": tag_id
            })

        self.update_tag_table()  # 読み込み後に表を更新

    def edit_tags(self):
        tag_win = tk.Toplevel(self.root)
        tag_win.title("タグ編集")

        def pick_color():
            _, hex_color = colorchooser.askcolor()
            if hex_color:
                new_color_entry.delete(0, tk.END)
                new_color_entry.insert(0, hex_color)

        def add_tag():
            tag = new_tag_entry.get().strip()
            color = new_color_entry.get().strip()
            if tag and color:
                if tag not in self.tag_colors:
                    self.tag_colors[tag] = color
                    self.update_tag_buttons()
                    self.save_tags_to_file()
                    messagebox.showinfo("追加完了", f"タグ '{tag}' を追加しました")
                else:
                    messagebox.showwarning("重複", "すでにそのタグは存在します")

        tk.Label(tag_win, text="タグ名:").grid(row=0, column=0)
        new_tag_entry = tk.Entry(tag_win)
        new_tag_entry.grid(row=0, column=1)

        tk.Label(tag_win, text="色:").grid(row=1, column=0)
        new_color_entry = tk.Entry(tag_win)
        new_color_entry.grid(row=1, column=1)

        tk.Button(tag_win, text="色を選択", command=pick_color).grid(row=1, column=2)
        tk.Button(tag_win, text="追加", command=add_tag).grid(row=2, column=0, columnspan=2, pady=5)

    def load_tags(self):
        if os.path.exists(self.TAGS_FILE):
            with open(self.TAGS_FILE, "r", encoding="utf-8") as f:
                self.tag_colors = json.load(f)

    def save_tags_to_file(self):
        with open(self.TAGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.tag_colors, f, ensure_ascii=False, indent=2)

    def zoom_image(self, event):
        if self.image_path is None:
            return

        # 拡大・縮小の倍率を設定
        scale_step = 0.1
        if event.delta > 0:  # ホイールアップで拡大
            self.scale += scale_step
        elif event.delta < 0:  # ホイールダウンで縮小
            self.scale = max(self.scale - scale_step, 0.1)  # スケールが0以下にならないように

        # 画像を再描画
        image = Image.open(self.image_path)
        new_size = (int(image.width * self.scale), int(image.height * self.scale))
        resized_image = image.resize(new_size, Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized_image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        # OCRで検出された矩形も再描画
        for item in self.text_boxes:
            box = item["box"]
            x1, y1 = box[0]  # 左上の座標
            x2, y2 = box[1]  # 右下の座標

            scaled_box = [
                x1 * self.scale,
                y1 * self.scale,
                x2 * self.scale,
                y2 * self.scale
            ]

            color = self.tag_colors.get(item["tag"], "gray")
            rect_id = self.canvas.create_rectangle(
                scaled_box[0], scaled_box[1],
                scaled_box[2], scaled_box[3],
                outline=color, width=2, tags="box"
            )
            text_id = self.canvas.create_text(
                scaled_box[0], scaled_box[1] - 3,
                text=item["text"], anchor=tk.SW, fill=color, font=("Arial", 10, "bold")
            )
            tag_id = self.canvas.create_text(
                scaled_box[2], scaled_box[3] + 3,
                text=item["tag"], anchor=tk.NE, fill=color, font=("Arial", 10, "bold")
            )
            item.update({"rect_id": rect_id, "text_id": text_id, "tag_id": tag_id})

    def fit_to_canvas(self):
        if self.image_path is None:
            return

        image = Image.open(self.image_path)
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        scale_x = canvas_width / image.width
        scale_y = canvas_height / image.height
        self.scale = min(scale_x, scale_y)

        # 画像を再描画
        new_size = (int(image.width * self.scale), int(image.height * self.scale))
        resized_image = image.resize(new_size, Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized_image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        # OCRで検出された矩形も再描画
        for item in self.text_boxes:
            box = item["box"]
            x1, y1 = box[0]  # 左上の座標
            x2, y2 = box[1]  # 右下の座標

            scaled_box = [
                x1 * self.scale,
                y1 * self.scale,
                x2 * self.scale,
                y2 * self.scale
            ]

            color = self.tag_colors.get(item["tag"], "gray")
            rect_id = self.canvas.create_rectangle(
                scaled_box[0], scaled_box[1],
                scaled_box[2], scaled_box[3],
                outline=color, width=2, tags="box"
            )
            text_id = self.canvas.create_text(
                scaled_box[0], scaled_box[1] - 3,
                text=item["text"], anchor=tk.SW, fill=color, font=("Arial", 10, "bold")
            )
            tag_id = self.canvas.create_text(
                scaled_box[2], scaled_box[3] + 3,
                text=item["tag"], anchor=tk.NE, fill=color, font=("Arial", 10, "bold")
            )
            item.update({"rect_id": rect_id, "text_id": text_id, "tag_id": tag_id})

    def show_tag_table(self):
        table_window = tk.Toplevel(self.root)
        table_window.title("タグ情報")

        frame = tk.Frame(table_window)
        frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(frame)
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ヘッダー行
        headers = ["X1", "Y1", "文字列", "タグ名"]
        for col, header in enumerate(headers):
            tk.Label(scrollable_frame, text=header, borderwidth=1, relief="solid", width=15).grid(row=0, column=col)

        # データ行
        for row, item in enumerate(self.text_boxes, start=1):
            x1, y1 = item["box"][0]
            tk.Label(scrollable_frame, text=f"{x1:.2f}", borderwidth=1, relief="solid", width=15).grid(row=row, column=0)
            tk.Label(scrollable_frame, text=f"{y1:.2f}", borderwidth=1, relief="solid", width=15).grid(row=row, column=1)
            tk.Label(scrollable_frame, text=item["text"], borderwidth=1, relief="solid", width=15).grid(row=row, column=2)
            tk.Label(scrollable_frame, text=item["tag"], borderwidth=1, relief="solid", width=15).grid(row=row, column=3)

        table_window.geometry("600x400")

    def update_tag_table(self):
        for widget in self.table_inner_frame.winfo_children():
            widget.destroy()

        headers = ["X1,Y1", "テキスト", "タグ", "スコア"]  # ヘッダーを変更
        for col, header in enumerate(headers):
            tk.Label(self.table_inner_frame, text=header, borderwidth=1, relief="solid", width=15).grid(row=0, column=col)

        for row, item in enumerate(self.text_boxes, start=1):
            x1, y1 = item["box"][0]
            color = self.tag_colors.get(item["tag"], "black")  # タグの色を取得

            # X1, Y1 を1つのセルにまとめて整数で表示
            tk.Label(self.table_inner_frame, text=f"({int(x1)}, {int(y1)})", borderwidth=1, relief="solid", width=15, fg=color).grid(row=row, column=0)

            # テキストを編集可能に
            text_entry = tk.Entry(self.table_inner_frame, width=15, fg=color)
            text_entry.insert(0, item["text"])
            text_entry.grid(row=row, column=1)

            def update_text(event, item=item, entry=text_entry):
                new_text = entry.get()
                item["text"] = new_text
                self.canvas.itemconfig(item["text_id"], text=new_text)

            text_entry.bind("<FocusOut>", update_text)

            # タグ名
            tk.Label(self.table_inner_frame, text=item["tag"], borderwidth=1, relief="solid", width=15, fg=color).grid(row=row, column=2)

            # スコア
            tk.Label(self.table_inner_frame, text=f"{item['score']:.2f}", borderwidth=1, relief="solid", width=15, fg=color).grid(row=row, column=3)

if __name__ == "__main__":
    root = tk.Tk()
    app = BIFTagger(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.save_tags_to_file(), root.destroy()))
    root.mainloop()

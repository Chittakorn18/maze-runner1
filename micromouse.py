import os
import random
import sys
import select
from collections import deque

try:
    import termios
    import tty
except ImportError:
    termios = None
    tty = None

# =====================================================================
# ⚙️ Configuration
# =====================================================================
# ล็อค Seed เพื่อให้สุ่มสนามออกมาได้หน้าตาเหมือนเดิมทุกครั้งที่รัน
# (หากวันตรวจคะแนน อาจารย์สามารถเปลี่ยนเลข 2026 เป็นเลขอื่นเพื่อจัดสอบ Unseen Maze ได้)
MAZE_SEED = 2026 

# =====================================================================
# 🏛️ คลาสระบบจำลองสนาม (Maze Simulator 30x30)
# (นักศึกษาห้ามแก้ไขส่วนนี้)
# =====================================================================
class MazeSimulator30x30:
    def __init__(self, size=30, min_steps=30, seed=None):
        self.size = size
        self.min_steps = min_steps
        self.cell_scale_cm = 16  # 1 ช่อง = 16 เซนติเมตร
        
        if seed is not None:
            random.seed(seed)
            
        # สร้างสนามตามเงื่อนไข (ขอบสนาม, มีทางออก, ระยะทางอย่างน้อย 30 ก้าว)
        self.maze, self.start_pos, self.cheese_pos, self.shortest_path_len = self.generate_valid_maze()
        
        self.mouse_pos = tuple(self.start_pos)
        self.was_collision = False
        self.step_count = 0
        self.max_steps = 1500  # ขีดจำกัดก้าวสูงสุด

    def generate_valid_maze(self):
        """ สุ่มสร้างเขาวงกตขนาด 30x30 โดยจุดเริ่ม/จุดจบอยู่ที่ขอบ และห่างกันอย่างน้อย 30 ก้าว """
        while True:
            # 1 = กำแพง, 0 = ทางเดิน
            maze = [[1 for _ in range(self.size)] for _ in range(self.size)]
            
            # เจาะสุ่มพื้นที่ภายในสนาม
            for r in range(1, self.size - 1):
                for c in range(1, self.size - 1):
                    if random.random() > 0.38:
                        maze[r][c] = 0
            
            # สุ่มจุดเริ่มและจุดจบให้อยู่ขอบสนามคนละฝั่ง
            edges = [0, 1, 2, 3] # 0:บน, 1:ล่าง, 2:ซ้าย, 3:ขวา
            start_edge = random.choice(edges)
            end_edge = random.choice([e for e in edges if e != start_edge])
            
            def get_edge_pos(edge):
                if edge == 0: return (0, random.randint(1, self.size - 2))
                if edge == 1: return (self.size - 1, random.randint(1, self.size - 2))
                if edge == 2: return (random.randint(1, self.size - 2), 0)
                if edge == 3: return (random.randint(1, self.size - 2), self.size - 1)

            start = get_edge_pos(start_edge)
            cheese = get_edge_pos(end_edge)
            
            maze[start[0]][start[1]] = 0
            maze[cheese[0]][cheese[1]] = 0

            # ตรวจสอบหาเส้นทางสั้นที่สุดด้วย BFS
            path_len = self.find_shortest_path(maze, start, cheese)
            if path_len >= self.min_steps:
                return maze, start, cheese, path_len

    def find_shortest_path(self, maze, start, end):
        queue = deque([(start[0], start[1], 0)])
        visited = {start}
        while queue:
            r, c, dist = queue.popleft()
            if (r, c) == end:
                return dist
            for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                nr, nc = r + dr, c + dc
                if (0 <= nr < self.size) and (0 <= nc < self.size):
                    if maze[nr][nc] == 0 and (nr, nc) not in visited:
                        visited.add((nr, nc))
                        queue.append((nr, nc, dist + 1))
        return -1

    def print_maze(self):
        """ แสดงผลภาพสนามเขาวงกตออกทางหน้าจอ Console """
        output = []
        for r in range(self.size):
            row_str = ""
            for c in range(self.size):
                if (r, c) == self.mouse_pos:
                    row_str += " M "  # หนู (Mouse)
                elif (r, c) == self.cheese_pos:
                    row_str += " 🧀"  # ชีส (Goal)
                elif self.maze[r][c] == 1:
                    row_str += "███"  # กำแพง (Wall)
                else:
                    row_str += " . "  # ทางเดิน (Path)
            output.append(row_str)
        print("\n".join(output), flush=True)
        print(f"📍 ตำแหน่งหนู: {tuple(self.mouse_pos)} | ก้าวที่: {self.step_count}", flush=True)

    def run_simulation(self, mouse_algo):
        print("==================================================")
        print(f"🎬 เริ่มต้นการทดสอบสนามขนาด {self.size}x{self.size} ช่อง (สเกล 1 ช่อง = {self.cell_scale_cm} cm)")
        print(f"📏 ระยะทางที่สั้นที่สุดที่เป็นไปได้สำหรับด่านนี้: {self.shortest_path_len} ก้าว")
        print("==================================================")
        
        print("\n[🗺️ แผนที่เขาวงกตเริ่มต้น]")
        self.print_maze()
        
        try:
            while self.mouse_pos != self.cheese_pos and self.step_count < self.max_steps:
                # 1. คำนวณระยะขจัด (Manhattan Distance) เป็นหน่วยเซนติเมตร
                dx = abs(self.mouse_pos[0] - self.cheese_pos[0])
                dy = abs(self.mouse_pos[1] - self.cheese_pos[1])
                distance_cm = (dx + dy) * self.cell_scale_cm
                
                print(f"\n[⏳ ก้าวที่ {self.step_count + 1} | รอคำสั่ง W/A/S/D หรือ q]")
                self.print_maze()
                
                # 2. ส่งค่าเข้าฟังค์ชั่นควบคุมของนักศึกษา (รับแค่ ระยะกลิ่น และ สถานะชน)
                action = mouse_algo.control_function(distance_cm, self.was_collision)
                
                # 3. อัปเดตการเคลื่อนที่ในระบบ
                row, col = self.mouse_pos
                new_row, new_col = row, col

                if action == 'UP': new_row -= 1
                elif action == 'DOWN': new_row += 1
                elif action == 'LEFT': new_col -= 1
                elif action == 'RIGHT': new_col += 1
                
                # ตรวจสอบขอบเขตและการชนกำแพง
                if (0 <= new_row < self.size) and (0 <= new_col < self.size) and self.maze[new_row][new_col] != 1:
                    self.mouse_pos = (new_row, new_col)
                    self.was_collision = False
                else:
                    self.was_collision = True # ชนกำแพง (ตำแหน่งเดิม)
                    
                self.step_count += 1
                print("\n[🔄 แผนที่หลังจากการเคลื่อนที่ครั้งที่ %d]" % self.step_count)
                self.print_maze()
        except KeyboardInterrupt:
            print("\n[⏹️ ยกเลิกการเดินด้วยผู้ใช้]")

        print("\n==================================================")
        print("--- 🏁 ผลการทดสอบ 🏁 ---")
        if self.mouse_pos == self.cheese_pos:
            actual_dist_m = (self.step_count * self.cell_scale_cm) / 100
            print(f"🎉 SUCCESS: หนูเดินทางถึงเป้าหมายสำเร็จ!")
            print(f"⏱️ จำนวนก้าวที่ใช้จริง: {self.step_count} ก้าว (ขั้นต่ำที่เป็นไปได้คือ {self.shortest_path_len} ก้าว)")
            print(f"🏃 ระยะทางวิ่งรวมในโลกจริง: {actual_dist_m:.2f} เมตร")
        else:
            print(f"❌ FAIL: หนูหลงทางหรือเดินชนจนหมดแรงครบ {self.max_steps} ก้าว")
        print("==================================================")
        
        print("[🗺️ แผนที่สรุปหลังจบเกม]")
        self.print_maze()


# =====================================================================
# 🎯 ส่วนที่นักศึกษาต้องนำไปออกแบบ Logic (Student Workspace)
# =====================================================================
class StudentMouseAlgorithm:
    def __init__(self, mode="auto"):
        """
        เจี๊ยกปรับให้เป็นโหมด Auto ร่างทอง ดมกลิ่นชีสได้!
        """
        self.mode = "auto"
        
        # ระบบสมองกลของหนู 
        self.pos = (0, 0)
        self.visited = {self.pos}
        self.walls = set()
        self.path = [self.pos] # Stack สำหรับถอยหลัง (Backtrack)
        
        self.last_action = None
        self.last_intended_pos = None
        
        # ตัวแปรใหม่: เอาไว้จำกลิ่นและเดาทิศทางชีส
        self.last_distance = None 
        self.pref_r = 0 # ทิศทางแกนตั้ง (1 = ลง, -1 = ขึ้น)
        self.pref_c = 0 # ทิศทางแกนนอน (1 = ขวา, -1 = ซ้าย)
        
        # Map คำสั่งทิศทางเข้ากับพิกัดจำลอง (Row, Col) 
        self.dir_map = {
            'UP': (-1, 0),     
            'DOWN': (1, 0),    
            'LEFT': (0, -1),   
            'RIGHT': (0, 1)    
        }
        self._control_hint_shown = False

    def control_function(self, distance_to_cheese, was_collision):
        """
        ฟังค์ชั่นควบคุมการเคลื่อนที่ของหนู 
        ใช้ Greedy DFS โดยอิงจากระยะห่างชีสที่เปลี่ยนไป
        """
        if not self._control_hint_shown:
            print("[🧠 โหมด Auto ร่างทอง: Greedy DFS ดมกลิ่นชีสฉบับเจี๊ยก!]", flush=True)
            self._control_hint_shown = True

        # 1. เรียนรู้จากก้าวที่แล้ว + อัปเดตทิศทางที่คิดว่าชีสอยู่
        if self.last_action is not None:
            if was_collision:
                # ชนกำแพง จดจำไว้
                self.walls.add(self.last_intended_pos)
            else:
                # เดินผ่าน อัปเดตตำแหน่ง
                self.pos = self.last_intended_pos
                if self.pos not in self.visited:
                    self.visited.add(self.pos)
                    self.path.append(self.pos)
                
                # *** ทีเด็ด: ถ้าระยะห่างชีสเปลี่ยนไป เอามาเดาทิศทาง! ***
                if self.last_distance is not None:
                    delta_d = distance_to_cheese - self.last_distance
                    dr, dc = self.dir_map[self.last_action]
                    
                    if delta_d < 0: # เข้าใกล้ชีส แปลว่ามาถูกทิศแล้ว!
                        if dr != 0: self.pref_r = dr
                        if dc != 0: self.pref_c = dc
                    elif delta_d > 0: # ออกห่างชีส แปลว่าชีสอยู่ทิศตรงข้าม!
                        if dr != 0: self.pref_r = -dr
                        if dc != 0: self.pref_c = -dc
                        
        self.last_distance = distance_to_cheese

        # 2. มองหาช่องรอบตัวที่ "ยังไม่เคยไป" และ "ไม่ใช่กำแพง"
        r, c = self.pos
        unvisited_neighbors = []
        
        for action, (dr, dc) in self.dir_map.items():
            next_pos = (r + dr, c + dc)
            if next_pos not in self.visited and next_pos not in self.walls:
                unvisited_neighbors.append((action, next_pos))

        # 3. ตัดสินใจก้าวต่อไปแบบคนฉลาด (Greedy Choice)
        if unvisited_neighbors:
            # ให้คะแนนแต่ละทิศ ทิศไหนชี้ไปทางชีส ให้คะแนนเยอะ!
            def score(act):
                d_r, d_c = self.dir_map[act]
                s = 0
                if d_r != 0 and d_r == self.pref_r: s += 1
                if d_c != 0 and d_c == self.pref_c: s += 1
                return s
            
            # เรียงลำดับตัวเลือกตามคะแนน (มากไปน้อย)
            unvisited_neighbors.sort(key=lambda x: score(x[0]), reverse=True)
            
            # ลุยไปทิศที่คะแนนเยอะสุดก่อน
            action, next_pos = unvisited_neighbors[0]
            self.last_intended_pos = next_pos
            self.last_action = action
            return action
        else:
            # ทางตันแล้ว The Peak! ต้อง Backtrack ถอยหลังตามระเบียบ
            if len(self.path) > 1 and self.path[-1] == self.pos:
                self.path.pop() 
            
            if not self.path:
                return 'UP' 
                
            target_pos = self.path[-1] 
            tr, tc = target_pos
            dr, dc = tr - r, tc - c
            
            back_action = None
            for act, (d_r, d_c) in self.dir_map.items():
                if (d_r, d_c) == (dr, dc):
                    back_action = act
                    break
            
            self.last_intended_pos = target_pos
            self.last_action = back_action
            return back_action

# =====================================================================
# 🚀 รันระบบทดสอบ (Main Execution)
# =====================================================================
if __name__ == "__main__":
    print("เลือกโหมดควบคุม:")
    print("1. Manual Control  (ให้ผู้ใช้กด W/A/S/D)")
    print("2. Random Control  (ใช้เพื่อสอน path planning)")
    choice = input("เลือก 1 หรือ 2 [1]: ").strip().lower()
    mode = "manual" if choice not in {"2", "random"} else "random"

    # 1. สร้างสนามแบบสุ่มแต่คงเดิมด้วย Seed ที่กำหนด
    sim = MazeSimulator30x30(size=30, min_steps=30, seed=MAZE_SEED)
    
    # 2. นำโค้ดอัลกอริทึมของนักศึกษาเข้ามาทดสอบ
    student_controller = StudentMouseAlgorithm(mode=mode)
    
    # 3. รันการจำลอง
    sim.run_simulation(student_controller)
"""
Nätverksvisualisering för StudyBuddy
Hanterar PyVis-grafvisualisering
"""
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network
import tempfile
import os
import json
from typing import Dict, List, Optional, Tuple


class NetworkVisualizer:
    """Hanterar nätverksvisualisering med PyVis"""
    
    def __init__(self):
        """Initialiserar visualiseraren"""
        self.default_physics = {
            "solver": "barnesHut",
            "barnesHut": {
                "gravitationalConstant": -8000,
                "centralGravity": 0.3,
                "springLength": 120,
                "springConstant": 0.04,
                "damping": 0.09,
                "avoidOverlap": 0.1
            },
            "maxVelocity": 50,
            "minVelocity": 0.1,
            "timestep": 0.5,
            "stabilization": {
                "enabled": True,
                "iterations": 1000,
                "updateInterval": 50
            }
        }
    
    def create_network(
        self, 
        height: str = "600px", 
        width: str = "100%",
        bgcolor: str = "#ffffff",
        font_color: str = "#1d1d1f",
        physics_enabled: bool = True,
        custom_physics: Optional[Dict] = None
    ) -> Network:
        """
        Skapar ett nytt PyVis-nätverk
        
        Args:
            height: Höjd på visualiseringen
            width: Bredd på visualiseringen
            bgcolor: Bakgrundsfärg
            font_color: Textfärg
            physics_enabled: Om fysik ska vara aktiverat
            custom_physics: Anpassade fysikinställningar
            
        Returns:
            Network-objekt
        """
        net = Network(height=height, width=width, bgcolor=bgcolor, font_color=font_color)
        
        if physics_enabled:
            physics = custom_physics or self.default_physics
            net.set_options(json.dumps({
                "physics": physics,
                "nodes": {
                    "font": {"size": 14},
                    "borderWidth": 2,
                    "shadow": True
                },
                "edges": {
                    "width": 2,
                    "shadow": True,
                    "smooth": {
                        "type": "continuous",
                        "roundness": 0.5
                    }
                },
                "interaction": {
                    "hover": True,
                    "multiselect": True,
                    "navigationButtons": True,
                    "keyboard": True
                }
            }))
        
        return net
    
    def add_nodes_and_edges(
        self, 
        net: Network, 
        nodes: List[Dict], 
        edges: List[Dict]
    ):
        """
        Lägger till noder och kanter till nätverket
        
        Args:
            net: PyVis Network-objekt
            nodes: Lista med noddata
            edges: Lista med kantdata
        """
        # Lägg till noder
        for node in nodes:
            net.add_node(
                node.get('id'),
                label=node.get('label', node.get('id')),
                color=node.get('color', '#97C2FC'),
                size=node.get('size', 25),
                title=node.get('title', node.get('label', '')),
                shape=node.get('shape', 'dot'),
                x=node.get('x'),
                y=node.get('y'),
                physics=node.get('physics', True)
            )
        
        # Lägg till kanter
        for edge in edges:
            net.add_edge(
                edge.get('from'),
                edge.get('to'),
                title=edge.get('label', ''),
                color=edge.get('color', '#848484'),
                width=edge.get('width', 2),
                arrows=edge.get('arrows'),
                dashes=edge.get('dashes', False)
            )
    
    def display_graph(
        self,
        nodes: List[Dict],
        edges: List[Dict],
        height: str = "600px",
        physics_enabled: bool = True,
        custom_physics: Optional[Dict] = None,
        key: Optional[str] = None
    ):
        """
        Visar grafen i Streamlit
        
        Args:
            nodes: Lista med noder
            edges: Lista med kanter
            height: Höjd på visualiseringen
            physics_enabled: Om fysik ska vara aktiverat
            custom_physics: Anpassade fysikinställningar
            key: Unik nyckel för komponenten
        """
        # Skapa nätverk
        net = self.create_network(
            height=height,
            physics_enabled=physics_enabled,
            custom_physics=custom_physics
        )
        
        # Lägg till noder och kanter
        self.add_nodes_and_edges(net, nodes, edges)
        
        # Spara till temporär fil
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as tmp:
            # Lägg till callback för interaktion
            net.write_html(tmp.name, notebook=False)
            
            # Läs HTML och modifiera för callbacks
            with open(tmp.name, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Injicera callback-kod
            callback_script = """
            <script>
            network.on("selectNode", function(params) {
                if (params.nodes.length > 0) {
                    const nodeId = params.nodes[0];
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue',
                        key: '""" + (key or 'network_selection') + """',
                        value: {selected_node: nodeId}
                    }, '*');
                }
            });
            
            network.on("selectEdge", function(params) {
                if (params.edges.length > 0) {
                    const edgeId = params.edges[0];
                    const edge = network.body.data.edges.get(edgeId);
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue',
                        key: '""" + (key or 'network_selection') + """',
                        value: {selected_edge: {from: edge.from, to: edge.to}}
                    }, '*');
                }
            });
            </script>
            """
            
            # Lägg till callback-skriptet före </body>
            html_content = html_content.replace("</body>", callback_script + "</body>")
            
            # Visa i Streamlit
            components.html(html_content, height=int(height.replace("px", "")) + 50)
            
            # Rensa temporär fil
            os.unlink(tmp.name)
    
    def create_hierarchical_layout(
        self,
        nodes: List[Dict],
        edges: List[Dict],
        direction: str = "UD"  # UD (Up-Down), DU, LR, RL
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Skapar en hierarkisk layout för noder
        
        Args:
            nodes: Lista med noder
            edges: Lista med kanter
            direction: Riktning för layouten
            
        Returns:
            Uppdaterade noder och kanter
        """
        # Implementera enkel hierarkisk positionering
        levels = {}
        
        # Hitta rotnoder (noder utan inkommande kanter)
        incoming = {node['id']: 0 for node in nodes}
        for edge in edges:
            incoming[edge['to']] = incoming.get(edge['to'], 0) + 1
        
        # Tilldela nivåer
        current_level = 0
        remaining = set(node['id'] for node in nodes)
        
        while remaining:
            # Hitta noder utan inkommande kanter från återstående noder
            level_nodes = []
            for node_id in remaining:
                if incoming.get(node_id, 0) == 0:
                    level_nodes.append(node_id)
                    levels[node_id] = current_level
            
            if not level_nodes:
                # Om vi har cykler, placera återstående noder på nästa nivå
                for node_id in remaining:
                    levels[node_id] = current_level
                break
            
            # Ta bort dessa noder och uppdatera inkommande räknare
            for node_id in level_nodes:
                remaining.remove(node_id)
                # Minska räknare för noder som denna pekar på
                for edge in edges:
                    if edge['from'] == node_id and edge['to'] in remaining:
                        incoming[edge['to']] -= 1
            
            current_level += 1
        
        # Uppdatera nodpositioner baserat på nivåer
        level_counts = {}
        for node_id, level in levels.items():
            level_counts[level] = level_counts.get(level, 0) + 1
        
        level_positions = {level: 0 for level in level_counts}
        
        updated_nodes = []
        for node in nodes:
            node_id = node['id']
            level = levels.get(node_id, 0)
            
            # Beräkna position
            if direction in ["UD", "DU"]:
                x = (level_positions[level] - level_counts[level] / 2) * 150
                y = level * 150 if direction == "UD" else -level * 150
            else:  # LR eller RL
                x = level * 150 if direction == "LR" else -level * 150
                y = (level_positions[level] - level_counts[level] / 2) * 150
            
            level_positions[level] += 1
            
            updated_node = node.copy()
            updated_node['x'] = x
            updated_node['y'] = y
            updated_node['physics'] = False  # Stäng av fysik för fixerad layout
            updated_nodes.append(updated_node)
        
        return updated_nodes, edges
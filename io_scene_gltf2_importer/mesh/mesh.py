"""
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 *
 * Contributor(s): Julien Duroure.
 *
 * ***** END GPL LICENSE BLOCK *****
 """

import bpy
import bmesh

from .primitive import *
from ..rig import *

class Mesh():
    def __init__(self, index, json, gltf):
        self.index = index
        self.json = json    # Mesh json
        self.gltf = gltf  # Reference to global glTF instance
        self.primitives = []
        self.target_weights = []
        self.name = None
        self.skin = None


    def read(self):
        if 'name' in self.json.keys():
            self.name = self.json['name']
            print("Mesh " + self.json['name'])
        else:
            print("Mesh index " + str(self.index))

        cpt_idx_prim = 0
        for primitive_it in self.json['primitives']:
            primitive = Primitive(cpt_idx_prim, primitive_it, self.gltf)
            primitive.read()
            self.primitives.append(primitive)
            primitive.debug_missing()
            cpt_idx_prim += 1

        # reading default targets weights if any
        if 'weights' in self.json.keys():
            for weight in self.json['weights']:
                self.target_weights.append(weight)

    def rig(self, skin_id, mesh_id):
        if skin_id not in self.gltf.skins.keys():
            self.skin = Skin(skin_id, self.gltf.json['skins'][skin_id], self.gltf)
            self.skin.mesh_id = mesh_id
            self.gltf.skins[skin_id] = self.skin
            self.skin.read()
            self.skin.debug_missing()
        else:
            self.skin = self.gltf.skins[skin_id]

    def blender_create(self):
        # Check if the mesh is rigged, and create armature if needed
        if self.skin:
            if self.skin.blender_armature_name is None:
                # Create empty armature for now
                self.skin.create_blender_armature(parent)

        # Geometry
        if self.name:
            mesh_name = self.name
        else:
            mesh_name = "Mesh_" + str(self.index)

        mesh = bpy.data.meshes.new(mesh_name)
        # TODO mode of primitive 4 for now.
        # TODO move some parts on mesh / primitive classes ?
        verts = []
        edges = []
        faces = []
        for prim in self.primitives:
            current_length = len(verts)
            prim_verts = [self.gltf.convert.location(vert) for vert in prim.attributes['POSITION']['result']]
            prim.vertices_length = len(prim_verts)
            verts.extend(prim_verts)
            prim_faces = []
            for i in range(0, len(prim.indices), 3):
                vals = prim.indices[i:i+3]
                new_vals = []
                for y in vals:
                    new_vals.append(y+current_length)
                prim_faces.append(tuple(new_vals))
            faces.extend(prim_faces)
            prim.faces_length = len(prim_faces)

            # manage material of primitive
            if prim.mat:

                # Create Blender material
                if not prim.mat.blender_material:
                    prim.mat.create_blender()

        mesh.from_pydata(verts, edges, faces)
        mesh.validate()


        # Normals
        offset = 0
        for prim in self.primitives:
            if 'NORMAL' in prim.attributes.keys():
                for poly in mesh.polygons:
                    for loop_idx in range(poly.loop_start, poly.loop_start + poly.loop_total):
                        vert_idx = mesh.loops[loop_idx].vertex_index
                        if vert_idx in range(offset, offset + prim.vertices_length):
                            if offset != 0:
                                cpt_vert = vert_idx % offset
                            else:
                                cpt_vert = vert_idx
                            mesh.vertices[vert_idx].normal = prim.attributes['NORMAL']['result'][cpt_vert]
        offset = offset + prim.vertices_length

        mesh.update()
        return mesh

    def blender_set_mesh(self, mesh, obj):

        # manage UV
        offset = 0
        for prim in self.primitives:
            for texcoord in [attr for attr in prim.attributes.keys() if attr[:9] == "TEXCOORD_"]:
                if not texcoord in mesh.uv_textures:
                    mesh.uv_textures.new(texcoord)
                    prim.blender_texcoord[int(texcoord[9:])] = texcoord

                for poly in mesh.polygons:
                    for loop_idx in range(poly.loop_start, poly.loop_start + poly.loop_total):
                        vert_idx = mesh.loops[loop_idx].vertex_index
                        if vert_idx in range(offset, offset + prim.vertices_length):
                            obj.data.uv_layers[texcoord].data[loop_idx].uv = Vector((prim.attributes[texcoord]['result'][vert_idx-offset][0], 1-prim.attributes[texcoord]['result'][vert_idx-offset][1]))

            offset = offset + prim.vertices_length

        mesh.update()

        # Object and UV are now created, we can set UVMap into material
        for prim in self.primitives:
            if prim.mat.pbr.color_type in [prim.mat.pbr.TEXTURE, prim.mat.pbr.TEXTURE_FACTOR] :
                prim.mat.set_uvmap(prim, obj)

        # Assign materials to mesh
        offset = 0
        cpt_index_mat = 0
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        for prim in self.primitives:
            obj.data.materials.append(bpy.data.materials[prim.mat.blender_material])
            for vert in bm.verts:
                if vert.index in range(offset, offset + prim.vertices_length):
                    for loop in vert.link_loops:
                        face = loop.face.index
                        bm.faces[face].material_index = cpt_index_mat
            cpt_index_mat += 1
            offset = offset + prim.vertices_length
        bm.to_mesh(obj.data)
        bm.free()

        # Create shapekeys if needed
        max_shape_to_create = 0
        for prim in self.primitives:
            if len(prim.targets) > max_shape_to_create:
                max_shape_to_create = len(prim.targets)

        # Create basis shape key
        if max_shape_to_create > 0:
            obj.shape_key_add("Basis")

        for i in range(max_shape_to_create):

            obj.shape_key_add("target_" + str(i))

            for prim in self.primitives:
                if i > len(prim.targets):
                    continue

                bm = bmesh.new()
                bm.from_mesh(mesh)

                shape_layer = bm.verts.layers.shape[i+1]
                vert_idx = 0
                for vert in bm.verts:
                    shape = vert[shape_layer]
                    co = self.gltf.convert.location(list(prim.targets[i]['POSITION']['result'][vert_idx]))
                    shape.x = obj.data.vertices[vert_idx].co.x + co[0]
                    shape.y = obj.data.vertices[vert_idx].co.y + co[1]
                    shape.z = obj.data.vertices[vert_idx].co.z + co[2]

                    vert_idx += 1

                bm.to_mesh(obj.data)
                bm.free()

        # set default weights for shape keys, and names
        for i in range(max_shape_to_create):
            if i < len(self.target_weights):
                obj.data.shape_keys.key_blocks[i+1].value = self.target_weights[i]
                if self.primitives[0].targets[i]['POSITION']['accessor'].name:
                   obj.data.shape_keys.key_blocks[i+1].name  = self.primitives[0].targets[i]['POSITION']['accessor'].name


        # Apply vertex color.
        vertex_color = None
        offset = 0
        for prim in self.primitives:
            if 'COLOR_0' in prim.attributes.keys():
                # Create vertex color, once only per object
                if vertex_color is None:
                    vertex_color = obj.data.vertex_colors.new("COLOR_0")

                color_data = prim.attributes['COLOR_0']['result']

                for poly in mesh.polygons:
                    for loop_idx in range(poly.loop_start, poly.loop_start + poly.loop_total):
                        vert_idx = mesh.loops[loop_idx].vertex_index
                        if vert_idx in range(offset, offset + prim.vertices_length):
                            if offset != 0:
                                cpt_idx = vert_idx % offset
                            else:
                                cpt_idx = vert_idx
                            vertex_color.data[loop_idx].color = color_data[cpt_idx][0:3]
                            #TODO : no alpha in vertex color
            offset = offset + prim.vertices_length

    def debug_missing(self):
        keys = [
                'name',
                'primitives',
                'weights'
                ]

        for key in self.json.keys():
            if key not in keys:
                print("MESH MISSING " + key)

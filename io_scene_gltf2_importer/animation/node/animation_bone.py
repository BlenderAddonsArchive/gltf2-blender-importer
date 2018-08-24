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
 * This development is done in strong collaboration with Airbus Defence & Space
 """

import bpy
from mathutils import Quaternion, Matrix, Vector

class AnimationBone():
    def __init__(self, animation):
        self.animation = animation

    def anim(self):
        obj   = bpy.data.objects[self.animation.gltf.skins[self.animation.node.skin_id].blender_armature_name]
        bone  = obj.pose.bones[self.animation.node.blender_bone_name]
        fps = bpy.context.scene.render.fps


        for anim in self.animation.anims.keys():
            if self.animation.gltf.animations[anim].name:
                name = self.animation.gltf.animations[anim].name + "_" + obj.name
            else:
                name = "Animation_" + str(self.animation.gltf.animations[anim].index) + "_" + obj.name
            if name not in bpy.data.actions:
                action = bpy.data.actions.new(name)
            else:
                action = bpy.data.actions[name]
            if not obj.animation_data:
                obj.animation_data_create()
            obj.animation_data.action = bpy.data.actions[action.name]

            for channel in self.animation.anims[anim]:
                if channel.path == "translation":
                    blender_path = "location"
                    for key in channel.data:
                        transform = Matrix.Translation(self.animation.gltf.convert.location(list(key[1])))
                        if not self.animation.node.parent:
                            mat = transform
                        else:
                            if not self.animation.gltf.scene.nodes[self.animation.node.parent].is_joint: # TODO if Node in another scene
                                mat = transform
                            else:
                                parent_mat = self.animation.gltf.scene.nodes[self.animation.node.parent].blender_bone_matrix

                                mat = (parent_mat.to_quaternion() * transform.to_quaternion()).to_matrix().to_4x4()
                                mat = Matrix.Translation(parent_mat.to_translation() + ( parent_mat.to_quaternion() * transform.to_translation() )) * mat

                        bone.location = self.animation.node.blender_bone_matrix.inverted() * mat.to_translation()
                        bone.keyframe_insert(blender_path, frame = key[0] * fps, group='location')


                    # Setting interpolation
                    for fcurve in [curve for curve in obj.animation_data.action.fcurves if curve.group.name == "rotation"]:
                        for kf in fcurve.keyframe_points:
                            self.animation.set_interpolation(channel.interpolation, kf)

                elif channel.path == "rotation":
                    blender_path = "rotation_quaternion"
                    for key in channel.data:
                        transform = (self.animation.gltf.convert.quaternion(key[1])).to_matrix().to_4x4()
                        if not self.animation.node.parent:
                            mat = transform
                        else:
                            if not self.animation.gltf.scene.nodes[self.animation.node.parent].is_joint: # TODO if Node in another scene
                                mat = transform
                            else:
                                parent_mat = self.animation.gltf.scene.nodes[self.animation.node.parent].blender_bone_matrix

                                mat = (parent_mat.to_quaternion() * transform.to_quaternion()).to_matrix().to_4x4()
                                mat = Matrix.Translation(parent_mat.to_translation() + ( parent_mat.to_quaternion() * transform.to_translation() )) * mat

                        bone.rotation_quaternion = self.animation.node.blender_bone_matrix.to_quaternion().inverted() * mat.to_quaternion()
                        bone.keyframe_insert(blender_path, frame = key[0] * fps, group='rotation')

                    # Setting interpolation
                    for fcurve in [curve for curve in obj.animation_data.action.fcurves if curve.group.name == "rotation"]:
                        for kf in fcurve.keyframe_points:
                            self.animation.set_interpolation(channel.interpolation, kf)


                elif channel.path == "scale":
                    blender_path = "scale"
                    for key in channel.data:
                        s = self.animation.gltf.convert.scale(list(key[1]))
                        transform = Matrix([
                            [s[0], 0, 0, 0],
                            [0, s[1], 0, 0],
                            [0, 0, s[2], 0],
                            [0, 0, 0, 1]
                        ])

                        if not self.animation.node.parent:
                            mat = transform
                        else:
                            if not self.animation.gltf.scene.nodes[self.animation.node.parent].is_joint: # TODO if Node in another scene
                                mat = transform
                            else:
                                parent_mat = self.animation.gltf.scene.nodes[self.animation.node.parent].blender_bone_matrix
                                mat = parent_mat.inverted() * transform

                        bone.scale = mat.to_scale()
                        bone.keyframe_insert(blender_path, frame = key[0] * fps, group='scale')

                    # Setting interpolation
                    for fcurve in [curve for curve in obj.animation_data.action.fcurves if curve.group.name == "rotation"]:
                        for kf in fcurve.keyframe_points:
                            self.animation.set_interpolation(channel.interpolation, kf)

import pyblish.api
from maya import cmds

from openpype.pipeline.publish import (
    PublishValidationError,
    ValidateContentsOrder
)


class ValidateSkeletonRigContents(pyblish.api.InstancePlugin):
    """Ensure skeleton rigs contains pipeline-critical content

    The rigs optionally contain at least two object sets:
        "skeletonAnim_SET" - Set of only bone hierarchies
        "skeletonMesh_SET" - Set of the skinned meshes
                             with bone hierarchies

    """

    order = ValidateContentsOrder
    label = "Skeleton Rig Contents"
    hosts = ["maya"]
    families = ["rig.fbx"]

    accepted_output = ["mesh", "transform", "locator"]
    accepted_controllers = ["transform", "locator"]

    def process(self, instance):
        objectsets = ["skeletonMesh_SET"]
        missing = [
            key for key in objectsets if key not in instance.data["rig_sets"]
        ]
        if missing:
            self.log.debug(
                "%s is missing sets: %s" % (instance, ", ".join(missing))
            )
            return

        # Ensure there are at least some transforms or dag nodes
        # in the rig instance
        set_members = instance.data['setMembers']
        if not cmds.ls(set_members, type="dagNode", long=True):
            self.log.debug("Skipping instance without dag nodes...")
            return
        # Ensure contents in sets and retrieve long path for all objects
        skeleton_mesh_content = instance.data.get("skeleton_mesh", [])
        skeleton_mesh_content = cmds.ls(skeleton_mesh_content, long=True)


        # Validate members are inside the hierarchy from root node
        root_node = cmds.ls(set_members, assemblies=True)
        hierarchy = cmds.listRelatives(root_node, allDescendents=True,
                                       fullPath=True)
        hierarchy = set(hierarchy)

        invalid_hierarchy = []
        if skeleton_mesh_content:
            for node in skeleton_mesh_content:
                if node not in hierarchy:
                    invalid_hierarchy.append(node)
            invalid_geometry = self.validate_geometry(skeleton_mesh_content)

        error = False
        if invalid_hierarchy:
            self.log.error("Found nodes which reside outside of root group "
                           "while they are set up for publishing."
                           "\n%s" % invalid_hierarchy)
            error = True

        if invalid_geometry:
            self.log.error("Only meshes can be part of the "
                           "skeletonMesh_SET\n%s" % invalid_geometry)
            error = True

        if error:
            raise PublishValidationError(
                "Invalid rig content. See log for details.")

    def validate_geometry(self, set_members):
        """Check if the out set passes the validations

        Checks if all its set members are within the hierarchy of the root
        Checks if the node types of the set members valid

        Args:
            set_members: list of nodes of the skeleton_mesh_set
            hierarchy: list of nodes which reside under the root node

        Returns:
            errors (list)
        """

        # Validate all shape types
        invalid = []
        shapes = cmds.listRelatives(set_members,
                                    allDescendents=True,
                                    shapes=True,
                                    fullPath=True) or []
        all_shapes = cmds.ls(set_members + shapes, long=True, shapes=True)
        for shape in all_shapes:
            if cmds.nodeType(shape) not in self.accepted_output:
                invalid.append(shape)

        return invalid
